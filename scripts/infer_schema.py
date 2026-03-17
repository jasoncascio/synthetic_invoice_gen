#!/usr/bin/env python3
"""
================================================================================
SYNTHETIC INVOICE GENERATOR - SCHEMA AUTO-INFER TOOL
================================================================================

This script reads a raw, sample JSON invoice payload and intelligently auto-generates 
a boilerplate `constraints.yaml` and `anomalies.yaml` configuration!

This is an enormous time-saver for domain experts. Instead of writing a 300-line 
YAML file by hand, simply pass in one good example invoice, let the script infer 
the Python data types, and tweak the mathematical bounds it sets up for you.

--------------------------------------------------------------------------------
USAGE INSTRUCTIONS:
--------------------------------------------------------------------------------
1. Save your sample invoice as a JSON file, e.g., `examples/sample.json`
   Example payload inside `examples/sample.json`:
   {
       "invoice_id": "INV-1004",
       "issue_date": "2026-03-01",
       "customer_name": "Acme Corp",
       "total_amount": 1500.50,
       "is_paid": false
   }

2. Run the script against your sample:
   $ python scripts/infer_schema.py --input examples/sample.json --out-dir config_output/

--------------------------------------------------------------------------------
PDF MULTI-MODAL EXTRACTION:
--------------------------------------------------------------------------------
If you have a raw PDF invoice instead of JSON, you can use the Google Gemini 
multimodal APIs to natively rip the PDF straight into a YAML schema!

Make sure you create a `.env` file in the project root containing your API key:
   GEMINI_API_KEY="your-key-here"

Then run:
   $ python scripts/infer_schema.py --pdf examples/real_invoice.pdf --out-dir config_output/

--------------------------------------------------------------------------------
EXPECTED OUTPUTS:
--------------------------------------------------------------------------------
The script will analyze your JSON types and emit two perfectly formatted files in 
the `--out-dir` folder:

1. `constraints_inferred.yaml`
   Will correctly map `issue_date` to `fake.date_this_year`, `total_amount` to 
   `random.uniform`, `is_paid` to `boolean`, and `invoice_id` to `string`.

2. `anomalies_inferred.yaml`
   Will automatically generate a boilerplate `drop` mutation on the first string 
   it finds (to test missing strings), and a `replace` mutation on the first 
   number it finds (to test mathematical mismatches).

================================================================================
"""

import json
import argparse
import os
import re

def is_date_format(s: str) -> bool:
    # Extremely basic heuristic checking for YYYY-MM-DD
    return bool(re.match(r"^\d{4}-\d{2}-\d{2}", str(s)))

def infer_constraints(json_payload: dict) -> dict:
    fields = {}
    for key, val in json_payload.items():
        if isinstance(val, bool):
            fields[key] = {
                "type": "boolean",
                "generator": "random.choice",
                "generator_args": {"seq": [True, False]},
                "example": val
            }
        elif isinstance(val, int):
            fields[key] = {
                "type": "integer",
                "generator": "random.randint",
                "generator_args": {"a": 1, "b": 100},
                "example": val
            }
        elif isinstance(val, float):
            fields[key] = {
                "type": "decimal",
                "generator": "random.uniform",
                "generator_args": {"a": 1.0, "b": 1000.0},
                "example": val
            }
        elif isinstance(val, str):
            if is_date_format(val):
                fields[key] = {
                    "type": "date",
                    "generator": "fake.date_this_year",
                    "example": val
                }
            elif "id" in key.lower() or "uuid" in key.lower():
                fields[key] = {
                    "type": "string",
                    "generator": "uuid.uuid4",
                    "example": val
                }
            else:
                fields[key] = {
                    "type": "string",
                    "generator": "fake.company" if "company" in key.lower() or "name" in key.lower() else "fake.word",
                    "example": val
                }
        else:
            fields[key] = {
                "type": "static",
                "value": str(val)
            }
            
    return {"locale": "en_US", "fields": fields}

def infer_anomalies(json_payload: dict) -> dict:
    mutations = []
    
    # 1. Grab first string to drop
    first_string = next((k for k, v in json_payload.items() if isinstance(v, str)), None)
    if first_string:
        mutations.append({
            "target": first_string,
            "action": "drop"
        })
        
    # 2. Grab first number to replace/corrupt
    first_number = next((k for k, v in json_payload.items() if isinstance(v, (int, float))), None)
    if first_number:
        mutations.append({
            "target": first_number,
            "action": "replace",
            "value": 0
        })

    return {"mutations": mutations}

def main():
    import yaml
    import sys
    
    parser = argparse.ArgumentParser(description="Infer YAML config from Sample JSON invoice")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--input", type=str, help="Path to sample JSON invoice file")
    group.add_argument("--pdf", type=str, help="Path to raw PDF invoice file (Requires GEMINI_API_KEY)")
    parser.add_argument("--out-dir", type=str, default=".", help="Directory to save the generated yaml files")
    args = parser.parse_args()

    os.makedirs(args.out_dir, exist_ok=True)
    
    if args.pdf:
        try:
            from google import genai
            from dotenv import load_dotenv
            load_dotenv()
        except ImportError:
            print("[Error] The google-genai or python-dotenv package is missing. Please `pip install -r requirements.txt`.")
            sys.exit(1)
            
        if "GEMINI_API_KEY" not in os.environ:
            print("[Error] The GEMINI_API_KEY environment variable was not found in your environment or a `.env` file.")
            sys.exit(1)
            
        client = genai.Client()
        print(f"Uploading {args.pdf} to Gemini API...")
        try:
            uploaded_file = client.files.upload(file=args.pdf)
            print("Structuring PDF semantic payload via gemini-2.5-flash...")
            response = client.models.generate_content(
                model='gemini-2.5-flash',
                contents=[
                    uploaded_file,
                    "You are an expert data extraction agent. Extract all header fields and line items from this invoice into a structured JSON dictionary. The 'line_items' key MUST be an array of objects. Return ONLY valid JSON, wrapped in standard markdown ```json blocks."
                ]
            )
            
            # Clean markdown formatting from the response
            raw_text = response.text
            match = re.search(r'```(?:json)?\s*(.*?)\s*```', raw_text, re.DOTALL | re.IGNORECASE)
            json_str = match.group(1) if match else raw_text
                
            payload = json.loads(json_str)
            print("[Success] Extracted raw JSON dictionary natively from PDF structure.")
            
        except Exception as e:
            print(f"\n[Error] Failed to process PDF via Gemini: {str(e)}\n")
            sys.exit(1)
    else:
        with open(args.input, 'r') as f:
            payload = json.load(f)
        
    constraints = infer_constraints(payload)
    anomalies = infer_anomalies(payload)
    
    constraints_path = os.path.join(args.out_dir, "constraints_inferred.yaml")
    with open(constraints_path, 'w') as f:
        yaml.dump(constraints, f, sort_keys=False, default_flow_style=False)
        
    anomalies_path = os.path.join(args.out_dir, "anomalies_inferred.yaml")
    with open(anomalies_path, 'w') as f:
        yaml.dump(anomalies, f, sort_keys=False, default_flow_style=False)
        
    print(f"\n[Success] Schema Auto-Inferred and written to Output Directory:")
    print(f" - Wrote Data Constraints: {constraints_path}")
    print(f" - Wrote Mutator Anomalies: {anomalies_path}\n")

if __name__ == "__main__":
    main()
