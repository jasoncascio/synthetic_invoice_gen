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
1. Save your sample invoice as a JSON file, e.g., `sample.json`
   Example payload inside `sample.json`:
   {
       "invoice_id": "INV-1004",
       "issue_date": "2026-03-01",
       "customer_name": "Acme Corp",
       "total_amount": 1500.50,
       "is_paid": false
   }

2. Run the script against your sample:
   $ python scripts/infer_schema.py --input sample.json --out-dir config_output/

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
    
    parser = argparse.ArgumentParser(description="Infer YAML config from Sample JSON invoice")
    parser.add_argument("--input", type=str, required=True, help="Path to sample JSON invoice file")
    parser.add_argument("--out-dir", type=str, default=".", help="Directory to save the generated yaml files")
    args = parser.parse_args()

    # Make output directory safely
    os.makedirs(args.out_dir, exist_ok=True)
    
    with open(args.input, 'r') as f:
        payload = json.load(f)
        
    constraints = infer_constraints(payload)
    anomalies = infer_anomalies(payload)
    
    constraints_path = os.path.join(args.out_dir, "constraints_inferred.yaml")
    with open(constraints_path, 'w') as f:
        # Avoid aliases in YAML output for clarity
        yaml.dump(constraints, f, sort_keys=False, default_flow_style=False)
        
    anomalies_path = os.path.join(args.out_dir, "anomalies_inferred.yaml")
    with open(anomalies_path, 'w') as f:
        yaml.dump(anomalies, f, sort_keys=False, default_flow_style=False)
        
    print(f"\n[Success] Schema Auto-Inferred from '{args.input}'")
    print(f" - Wrote Data Constraints: {constraints_path}")
    print(f" - Wrote Mutator Anomalies: {anomalies_path}\n")

if __name__ == "__main__":
    main()
