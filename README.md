# Synthetic Invoice Generator V2: Usage Guide

This document outlines how to install the project, execute the core generator pipeline, and test the outputs securely on your local machine.

📖 **Architecture & Design**: For a deep dive into the system architecture and future roadmap, see the **[System Design Document](docs/versions/2/synthetic_invoice_generator_v2_design.md)**.

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
python main.py --count 5000 --mutation-rate 0.15 --output-dir datasets/
```
In the example above, the engine will construct 5,000 synthetic invoices. Exactly 15% (750 invoices) will intercepted by the Mutator and corrupted according to your `anomalies.yaml` configuration, yielding a mathematically precise dataset for AI training.

### Pipeline Arguments
| Argument | Description | Default |
|----------|-------------|---------|
| `--config` | Path to the base `constraints.yaml` file. | `examples/constraints.yaml` |
| `--anomalies` | Path to the `anomalies.yaml` file for mutations. | `examples/anomalies.yaml` |
| `--value-spaces` | Path to the `value_spaces.yaml` file for lookups. | `examples/value_spaces.yaml` |
| `--count` | The total number of records to generate. | `10` |
| `--mutation-rate` | A decimal percentage (e.g., `0.10` for 10%) of records to mutate randomly. | `0.0` |
| `--seed` | A static integer to lock the randomization pools for deterministic QA reproduction. | None |
| `--preview` | Print exactly 1 JSON object to stdout and exit (overrides count/mutation rate). | `false` |
| `--output-format` | File format for outputs. Choose between `json-files`, `jsonl`, or `json-array`. | `json-files` |
| `--output-dir` | The destination folder or filepath for the generated dataset. | `output` |

---

## 4. Bootstrapping Configurations with AI (Schema Inference)
Writing massive YAML files by hand can be tedious. If you already have a `sample.json` invoice from the real world, you can provide it to our **Auto-Inference Tool**. This tool parses the `sample.json` document and automatically reverse-engineers a `constraints_inferred.yaml` boilerplate for you to start tweaking.

```bash
# 1. Provide a working sample JSON file
# 2. Run the inference utility
python scripts/infer_schema.py --input examples/sample.json --out-dir config_output/

# OR bypass JSON entirely: provide a raw unformatted PDF explicitly to 
# the gemini-2.5-flash multi-modal extraction engine!
# Note: You must have a `.env` file with GEMINI_API_KEY=... in this folder!
python scripts/infer_schema.py --pdf my_invoice.pdf --out-dir config_output/
```

This will automatically detect numbers, dates, strings, and arrays, instantly mapping them to native Python configurations in a brand new YAML document!

---

## 5. Configuration Formats

The Synthetic Invoice Generator relies on three YAML files to dictate data shape, statistical anomalies, and lookup values. Unlike static mock tools, this engine resolves fields dynamically using a **Directed Acyclic Graph (DAG)** and evaluates mathematical relations via an **AST Evaluator**.

---

### A. Constraints Configuration (`constraints.yaml`)

This file defines the base schema of your invoice. The engine reads all fields, determines their dependencies, and sorts them topologically so that variables are calculated in the correct chronological order.

#### 🧠 Key Concepts & Mechanics

1.  **DAG Dependency Resolution**: If `tax_amount` requires `subtotal`, the engine ensures `subtotal` is generated first.
2.  **Native Structuring**: You can nest schemas infinitely using `array` and `object` types. The generator recurses automatically.

#### 📋 Field Schema Definitions

-   **`type`** (required): The data type.
    -   Options: `string`, `integer`, `decimal`, `date`, `boolean`, `static`, `array`, `object`.
-   **`value`** (any): Required ONLY if `type: static`. Provides a hardcoded value.
-   **`generator`** (string): Standard Python or Faker library expression.
    -   *Example*: `"fake.name"`, `"random.choice"`, `"fake.company"`, `"value_space.random"`.
-   **`generator_args`** (dict): Keyword arguments passed to the generator.
    -   *Example*: `{ a: 1, b: 10 }` for `randint`.
-   **`dependencies`** (list of strings): List of sibling fields that must be generated *before* this field can compute.
-   **`computed`** (string): A mathematical or Pythonic expression evaluated via safe AST.
-   **`count_expr`** (string): Required for `type: array`. Python expression deciding how many elements to build (e.g., `random.randint(1, 5)`).
-   **`schema`** (object): Required for `type: array` or `type: object`. Defines inner fields using the same properties.

#### 🧮 The AST Evaluator (`computed` fields)

Computed fields use the `asteval` library, running a safe subset of Python. You cannot import dangerous system libraries, but you have access to standard operators and functions automatically:

-   **Operators**: Regular math (`+`, `-`, `*`, `/`), exponents (`**`), Modulo (`%`).
-   **Built-in Functions**: `round()`, `sum()`, `max()`, `min()`, `abs()`.
-   **Implicit Variables**: Any field listed in your `dependencies` array is available as a local variable.
-   **Modules Included**:
    -   `math`: (e.g., `math.sqrt()`, `math.ceil()`).
    -   `random`: (e.g., `random.uniform()`).

> [!NOTE]
> If you reference a variable in your `computed` string without declaring it in `dependencies`, the engine will throw a domain-specific `MissingReferenceError` rather than a raw Python traceback.

#### 📂 Example `constraints.yaml`

```yaml
locale: en_US

fields:
  invoice_id:
    type: string
    generator: "fake.pystr"
    generator_args:
      min_chars: 10
      max_chars: 10
      
  line_items:
    type: array
    count_expr: "random.randint(2, 5)"
    schema:
      description:
        type: string
        generator: "fake.catch_phrase"
      quantity:
        type: integer
        generator: "random.randint"
        generator_args: { a: 1, b: 20 }
      unit_price:
        type: decimal
        generator: "random.uniform"
        generator_args: { a: 10.0, b: 100.0 }
      line_total:
        type: decimal
        dependencies: [quantity, unit_price]
        computed: "round(quantity * unit_price, 2)"
        
  subtotal:
    type: decimal
    dependencies: [line_items]
    computed: "round(sum([float(item['line_total']) for item in line_items]), 2)"
```

---

### B. Anomalies Configuration (`anomalies.yaml`)

Anomalies intercept the *completed* generated document and forcefully overwrite data points. Because this happens *after* the base graph resolves, the corruption is isolated—the rest of the document remains mathematically consistent with the *pre-mutated* state, making it perfect for training AI detection systems!

#### 🧠 Key Concepts & Mechanics

1.  **Dot-Notation Targeting**: You target deep nested structures using indexes and properties.
    -   `subtotal` (Root level)
    -   `business_address.city` (Nested object property)
    -   `line_items[0].quantity` (Specific array index)
2.  **Independent Intercept**: The engine intercepts the deep dictionary without recalculating the rest of the sheet.

#### 📋 Mutation Schema Definitions

-   **`target`** (required, string): The dot-notation path to overwrite.
-   **`action`** (required, enum):
    -   `drop`: Completely removes the key/index.
    -   `replace`: Forces a static value or a dynamic evaluation.
    -   `modify`: Re-runs the generator for this field but requires specific constraints.
-   **`value`** (any): Used for `replace`. A static value.
-   **`value_computation`** (string): Used for `replace`. Dynamic AST expression.
-   **`rules`** (list of strings): Used for `modify`. A list of validations (e.g., `value < 0`).

#### 📂 Example `anomalies.yaml`

```yaml
mutations:
  # 1. Simple Drop
  - target: "invoice_id"
    action: drop

  # 2. Static Value Injection (creating a negative quantity anomaly)
  - target: "line_items[0].quantity"
    action: replace
    value: -10

  # 3. Dynamic Replace (doubling a price)
  - target: "line_items[1].unit_price"
    action: replace
    value_computation: "unit_price * 2"
```

---

### C. Value Spaces Configuration (`value_spaces.yaml`)

Value spaces are lightweight lookup tables. They allow you to pull from custom lists (e.g., approved vendors, SKUs, terms) rather than relying exclusively on random Faker strings.

You pair these in your `constraints.yaml` using the `value_space.random` generator.

#### 📂 Example `value_spaces.yaml`

```yaml
approved_vendors:
  - "Acme Corp"
  - "Initech Software"
  - "Globex Aerospace"
```

#### 🔗 Pairing with `constraints.yaml`

```yaml
fields:
  vendor_name:
    type: string
    generator: "value_space.random"
    generator_args:
      space: "approved_vendors"
      fallback: "fake.company" # Used if the space is missing or empty
```
