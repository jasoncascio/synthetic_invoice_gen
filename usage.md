# Synthetic Invoice Generator V2: Usage Guide

This document outlines how to install the project, execute the core generator pipeline, and test the outputs securely on your local machine.

---

## 1. Quick Start Installation
The project relies on standard Python virtual environments. There are no crazy system-level dependencies required.

> [!CAUTION]
> If you are on a restricted corporate proxy or VM, you may need to pass explicit `--trusted-host pypi.org` flags to `pip` if SSL failures occur during installation.

```bash
# 1. Create a virtual environment
python3 -m venv venv

# 2. Activate the environment
source venv/bin/activate  # On Windows: venv\Scripts\activate

# 3. Install core dependencies
pip install -r requirements.txt
```

---

## 2. Testing the Pipeline (The Preview Flag)
The easiest way to test your `constraints.yaml` and verify that the topological sorter and mathematical AST evaluator are working is to use the `--preview` flag.

The `--preview` flag instantly generates **exactly 1 base record**, injects mathematical anomalies (if configured), and prints the highly formatted JSON directly to your terminal. It bypasses exporting files to your hard drive, making it the perfect tool for rapid debugging and configuration iteration!

```bash
python main.py --preview
```

---

## 3. Bulk Generator Execution
Once your configuration is validated via `--preview`, you can execute bulk pipeline generation. The orchestrator allows you to firmly dictate exactly how many invoices are built and what percentage of those invoices contain engineered failures (anomalies).

```bash
python main.py --count 5000 --mutation-rate 0.15 --out-dir datasets/
```
In the example above, the engine will construct 5,000 synthetic invoices. Exactly 15% (750 invoices) will intercepted by the Mutator and corrupted according to your `anomalies.yaml` configuration, yielding a mathematically precise dataset for AI training.

### Pipeline Arguments
| Argument | Description | Default |
|----------|-------------|---------|
| `--count` | The total number of records to generate. | `1` |
| `--mutation-rate` | A decimal percentage (e.g., `0.10` for 10%) of records to mutate. | `0.0` |
| `--seed` | A static integer to lock the randomization pools for deterministic QA reproduction. | None |
| `--out-format` | The schema format of the output files. Choose between `json-files` (individual docs per invoice), `jsonl` (one massive file, separated by newlines), or `json-array` (one massive JSON array). | `json-files` |
| `--out-dir` | The destination folder for the generated dataset. | `output/` |

---

## 4. Bootstrapping Configurations with AI (Schema Inference)
Writing massive YAML files by hand can be tedious. If you already have a `sample.json` invoice from the real world, you can provide it to our **Auto-Inference Tool**. This tool parses the `sample.json` document and automatically reverse-engineers a `constraints_inferred.yaml` boilerplate for you to start tweaking.

```bash
# 1. Provide a working sample JSON file
# 2. Run the inference utility
python scripts/infer_schema.py --input examples/sample.json --out-dir config_output/

# OR bypass JSON entirely: provide a raw unformatted PDF explicitly to 
# the gemini-2.5-flash multi-modal extraction engine!
export GEMINI_API_KEY="your-api-key"
python scripts/infer_schema.py --pdf my_invoice.pdf --out-dir config_output/
```

This will automatically detect numbers, dates, strings, and arrays, instantly mapping them to native Python configurations in a brand new YAML document!
