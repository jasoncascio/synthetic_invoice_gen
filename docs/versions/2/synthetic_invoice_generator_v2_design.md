# V2 System Design Document: Synthetic Invoice Generator

## 1. Objective
To design and implement an automated, highly configurable pipeline capable of generating synthetic invoices alongside perfectly matched "ground truth" labels (JSON/CSV). Crucially, the system is meant to produce datasets used to train, test, and validate AI-based invoice agents.

The core principle of the generator is complete decoupling: data generation logic, schema definition, anomaly modeling, visual rendering, and export destination are all completely independent. It is designed to be fully configurable by domain experts without modifying a single line of Python codebase.

## 2. Architectural Strategy & Module Boundaries
The V2 system employs a **"Configuration-Driven, Data-First, Rendering-Agnostic"** strategy. The application operates as a standalone Python command line application and library (`synthetic_invoice_generator`). 

### Core Modules
The pipeline operates in 4 distinct phases executed by the orchestrator (`main.py`):
1. **Config Parser (`config/`):** Uses **Pydantic** to ingest `constraints.yaml` and `anomalies.yaml`, strictly typing and validating the user rules before execution begins. It optionally mounts an external `value_spaces.yaml` dictionary to provide valid categorical constants.
2. **Generation Engine (`engine/`):** Uses topological sorting (`graphlib` or `networkx`) to resolve dependencies. Evaluates AST strings and Fake/Random generators to yield an unmutated "Base Record".
3. **Mutator Engine (`mutator/`):** Applies the sequence of anomalies configured to the Base Record to yield failure-cases, stamping the record with `scenario_label`.
4. **I/O Subsystem (`io/`):** Passes the final record through a `Renderer` (Jinja PDF/JSON) and immediately proxies the byte streams into an `Exporter` (Local/Zip/GCS).

### 2.1 Expected Directory Structure (Implementation Blueprint)
To maintain the mandated decoupling, the codebase must strictly adhere to the following package topology during development:
```text
synthetic_invoice_generator_v2/
├── src/
│   ├── __init__.py
│   ├── config/          # Pydantic models (Schema Validation, Yaml Loading)
│   ├── engine/          # Topo-sorter, Faker wrappers, AST evaluator (`asteval`)
│   ├── mutator/         # ActionRegistry (drop, replace, modify handlers)
│   ├── io/              # Renderers (Jinja/JSON) & Exporters (Local/Zip/GCS)
│   └── plugins/         # Standardized SyntheticGeneratorPlugin interface
├── templates/           # (Future Plan) Optional Jinja HTML/CSS layout templates for PDF rendering
├── scripts/             # Python developer utilities (e.g., auto-infer schema tools)
├── main.py              # CLI Orchestrator and application entrypoint
└── requirements.txt
```

## 3. Configuration-Driven Rules (Generation Engine)
Base definitions, logical constraints, and value spaces are externalized entirely into `constraints.yaml`.

### 3.1 Field Generation via Topological Sort
Because fields depend on other fields (e.g., `line_total` depends on `quantity`), the generation engine must construct a **Directed Acyclic Graph (DAG)** of all fields in `constraints.yaml`.
- The engine computes the topological order of generation.
- If a cycle is detected during DAG construction, a `CyclicalDependencyError` is raised immediately before generation starts.
- Before generating user fields, the Engine silently injects forensic trace metadata (e.g., `_batch_id`, `_sequence_num`) into the base `context_record`, allowing every exported JSON/CSV file to be definitively tracked back to a specific generator execution. 
- Fields with no `dependencies` (e.g., `issue_date`) are evaluated first.

> *Implementation Hint: When evaluating AST `computed` strings or `rules` via the `asteval` sandbox later in the pipeline, the engine must dynamically inject the previously generated fields from the master `context_record` dictionary directly into the evaluator's `symtable`. This is what allows a raw python string like `"quantity * unit_price"` to resolve variables safely.*

## 4. Formal YAML Field Definition Syntax
To achieve maximum flexibility, each field in `constraints.yaml` follows a strict structure, validated by Pydantic before runtime. A field definition can utilize one of four primary generative approaches (`static`, `generator`, `computed`, or `plugin`).

> *Implementation Hint: The `config/` module should define a strict Pydantic model (e.g., `class FieldDefinition(BaseModel)`) that leverages `typing.Optional` extensively with `@root_validator` or `@model_validator` methods. This ensures that properties like `computed`, `generator`, and `rules` are mathematically mutually exclusive and strongly typed on startup before the DAG is even constructed.*

### 4.1 Data Generators Syntax (`generator:`)
The `generator` key dictates the underlying python engine used to randomly select the data before applying your bounded rules.
*   **Faker Methods**: Use the prefix `fake.`. The provider automatically pulls dictionaries constrained by the root YAML `locale` (e.g., `da_DK`).
    *   *Example*: `generator: "fake.date_this_year"`
    *   *Example*: `generator: "fake.company"`
*   **Standard Python Math/UUID**: Directly maps to native Python randomization pools.
    *   *Example*: `generator: "random.randint"`
    *   *Example*: `generator: "random.uniform"`
    *   *Example*: `generator: "uuid.uuid4"`
*   *(Optional Arguments)*: If the python generator requires explicit boundaries passed as parameters, they can be securely assigned via the `generator_args` dictionary payload.

#### 4.1.1 Modular Categorical Registries (Value Spaces)
Not all strings should be fully randomized by Faker. For strictly defined domain spaces (like an approved list of Customer Names, Tax Classifications, or SKUs), the engine natively integrates external, modular dictionaries.
*   **The Setup**: Users provide an optional `value_spaces.yaml` (e.g., `approved_customers: ["Acme Corp", "Globex"]`) alongside the `constraints.yaml`.
*   **The Generator**: Fields use the `value_space.random` generator to pull strictly from the modular dictionary. Crucially, the system supports an optional `fallback` mechanism. If `value_spaces.yaml` is not mounted or the requested `space` key is fundamentally undefined, the engine gracefully delegates to a designated Faker generator instead of throwing a runtime `KeyError`.
    *   *Example*: `generator: "value_space.random"`
    *   *Args*: `generator_args: { space: "approved_customers", fallback: "fake.company" }`

### 4.2 Data Constraint Rules Syntax (`rules:`)
Used to tightly bound numeric limits, date ranges, and conditionally generated text values. The `rules` block accepts a list of string-based constraints evaluated sequentially until the generator yields an aligned match.
*   **Relational Operators**: `>=`, `<=`, `>`, `<`, `==`, `!=`
    *   *Example*: `- ">= 100"`
    *   *Example*: `- "< issue_date"`
*   **Range & Membership**: `between <X> and <Y>`, `in <list>`, `not in <list>`
    *   *Example*: `- "between 1.00 and 1000.00"`
    *   *Example*: `- "in ['USD', 'DKK', 'EUR']"`
*   **Temporal Expressions**: Supported directly on Datetime variants using `+ Nd`, `- Nw`, `+ Nm` (Days, Weeks, Months offsets).
    *   *Example*: `- ">= issue_date + 14d"`

### 4.3 Computed Properties Syntax (`computed:`)
When a field is purely mathematically derived from previously generated dependencies, do not use a `generator`. Instead, rely on `computed` which enforces a secure Abstract Syntax Tree (AST-based `asteval`) equation.
*   **Dependencies Array**: You **must** meticulously list every referenced variable string in the `dependencies` array to ensure DAG resolution prevents runtime race conditions.
*   **Standard Arithmetic**: Supports `+`, `-`, `*`, `/`, `**`, and `()` grouping.
    *   *Example*: `computed: "(quantity * unit_price) + shipping_fee"`
*   **Ternary Conditions**: Supports inline pythonic logic (`X if Condition else Y`).
    *   *Example*: `computed: "line_total * 0.2 if tax_code == 'VAT' else 0"`
*   **Type Casting & Methods**: Core functions are whitelisted like `sum()`, `round(val, 2)`.
    *   *Security Limitation*: Attempts to inject arbitrary OS commands like `__import__('os')` inside a `computed` string will aggressively trigger an AST security exception framework, killing execution.

### 4.4 Advanced Plugins Syntax (`plugin:`)
When inline AST expressions become too massive or fragile (e.g., executing a database lookup or massive switch statement), the YAML supports yielding directly to an encapsulated Python Object interface. 
*   **Invocation**: Provide the dot-notation path directly to the class inside the `plugin` key. The Engine dynamically instantiates the Class.
*   **Contract Requirement**: The targeted Class must inherit from the platform's `SyntheticGeneratorPlugin` abstract base class and implement a functional `.generate(context_record)` method.

```yaml
fields:
  discount_amount:
    type: decimal
    dependencies: [customer_tier, line_total]
    plugin: "custom_plugins.DiscountCalculator"
```

### 4.5 Nested Arrays and Objects (`type: array`)
The engine recursively builds and evaluates topological structures natively. Instead of relying exclusively on Python Plugins for multi-line JSON structures (like `line_items`), you can explicitly declare `type: array` or `type: object`.
*   **Recursive Schema**: You must provide a nested `schema` dictionary of field constraints. The internal variables will mathematically compute against each other safely within their local scope.
*   **Dynamic Count**: By assigning a `count_expr` (e.g., `random.randint(1,4)`), the generator will natively evaluate your randomizer loops.

### 4.6 Consolidated YAML Example
Putting it all together, the exact reference specification looks like the following. Notice how the `constraints.yaml` maps beautifully to the optional `value_spaces.yaml` dictionary.

```yaml
# value_spaces.yaml (Optional Categorical Dictionary)
approved_customers:
  - "Acme Corp"
  - "Globex Corporation"
  - "Initech Software"
```

```yaml
# constraints.yaml
locale: da_DK

fields:
  # STATIC FIELD
  invoice_type:
    type: static
    value: "INVOICE"
    example: "INVOICE"
    
  # GENERATOR FIELD + RULES (Temporal)
  issue_date:
    type: date
    generator: "fake.date_this_year"
    example: "2026-03-01"

  due_date:
    type: date
    dependencies: [issue_date]
    rules:
      - ">= issue_date + 14d"
      - "<= issue_date + 60d"
    example: "2026-03-25"

  # GENERATOR FIELD + ARGS + RULES (Numeric)
  quantity:
    type: integer
    generator: "random.randint"
    generator_args:
      a: 1
      b: 100
    rules:
      - ">= 5"
    example: 5

  # GENERATOR FIELD (MODULAR VALUE SPACE WITH FALLBACK)
  customer_name:
    type: string
    generator: "value_space.random"
    generator_args:
      space: "approved_customers" # Evaluates against external value_spaces.yaml
      fallback: "fake.company"    # Triggers safely if external YAML is missing
    example: "Globex Corporation"

  unit_price:
    type: decimal
    generator: "random.uniform"
    generator_args:
      a: 1.00
      b: 1000.00
    example: 150.50

  # COMPUTED FIELD
  line_total:
    type: decimal
    dependencies: [quantity, unit_price]
    computed: "round(quantity * unit_price, 2)"
    example: 752.50
    
  # PLUGIN HOOK
  discount_amount:
    type: decimal
    dependencies: [customer_tier, line_total]
    plugin: "custom_plugins.DiscountCalculator"
    example: 200.00
```

### 4.7 Complete YAML Parameter Dictionary

The following table provides an exhaustive list of all reserved keys allowed within the `constraints.yaml` structure.

**Top-Level Configuration Keys**
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `locale` | *String* | Yes | Maps the generation engine and Faker to a specific regional format (e.g., `da_DK`, `en_US`). |
| `fields` | *Dictionary* | Yes | The root container for all field definitions. |

**Field-Level Keys (Nested under `fields.<field_name>`)**
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `type` | *String* | Yes | The target output type. Valid values: `string`, `integer`, `decimal`, `date`, `boolean`, `static`, `array`, `object`. |
| `value` | *Any* | Conditional | Required only if `type` is `static`. Hardcodes the final output value immediately. |
| `example` | *Any* | No | Passive metadata used exclusively for populating exported OpenAPI/JSON schemas. Ignored during data generation. |
| `dependencies` | *List[String]* | Conditional | A specifically ordered list of other field keys that must be securely generated *before* this field can evaluate its constraints or expressions. Required if `computed`, `rules`, or `plugin` references other fields. |
| `generator` | *String* | Conditional | The namespace target for randomization. Valid formats: `fake.<method>`, `random.<method>`, `uuid.<method>`, or `value_space.<method>`. |
| `generator_args`| *Dictionary* | No | Specific named keywords passed into the python `generator` (e.g., `a: 1`, `b: 100`, `space: "customer_names"`, `fallback: "fake.company"`). |
| `rules` | *List[String]* | No | A list of bounding validations evaluating sequentially. Generators will internally retry until all rules pass or a timeout occurs. |
| `computed` | *String* | Conditional | Evaluates an AST math string natively in place of a generator. Cannot be used simultaneously with `generator`. |
| `plugin` | *String* | Conditional | Overrides `generator` and `computed` to yield execution fully to a custom Python `SyntheticGeneratorPlugin` class natively imported via dot-notation. |
| `schema` | *Dictionary* | Conditional | A nested dictionary defining sub-fields. Strictly required if `type` is `array` or `object`. |
| `count_expr` | *String* | Conditional | An AST evaluated string dictating dynamic array length (e.g. `random.randint(1, 4)`). Strictly required if `type` is `array`. |

### 4.8 Actionable Exceptions & Debugging
To guarantee a frictionless setup experience for domain experts, the CLI is strictly designed to throw **actionable exceptions** during the Pydantic validation and DAG construction phases—catching errors *before* generation even starts. When an exception is raised, the console log must proactively explicitly suggest how to fix it.

> [!CAUTION]
> 1. **`ConstraintSatisfactionError`**: Occurs when rules are mutually exclusive (e.g., `[">= 100", "<= 10"]`). 
>    - *CLI Suggestion Message*: "Failed to generate 'quantity' after 500 attempts. Check your rules for mathematically impossible or conflicting boundaries."
> 2. **`MissingReferenceError`**: Occurs when you use a variable in `computed` or `rules` without listing it in `dependencies`.
>    - *CLI Suggestion Message*: "You referenced 'issue_date' in 'due_date' computation, but 'issue_date' is missing from the dependencies array. Please explicitly declare it in the YAML."
> 3. **`CyclicalDependencyError`**: Occurs when parsing the DAG if fields rely on each other (e.g., A -> B -> A).
>    - *CLI Suggestion Message*: "Cycle detected between 'line_total' and 'tax_amount'. A field cannot mathematically depend on itself. Please trace and remove the circular reference."
> 4. **`ExpressionSyntaxError`**: Occurs when evaluating malformed AST strings.
>    - *CLI Suggestion Message*: "Malformed python syntax in 'discount' computation: `(A + B * C`. Check for unbalanced parentheses or invalid python operators."

## 5. Pluggable Anomaly Injection (The Mutator)
After Stage 1 yields a 100% mathematically correct "base" record, Stage 2 utilizes an `ActionRegistry` driven by the `anomalies.yaml` configuration to intentionally corrupt the document. This generates explicit failure cases for your AI validation agents to catch.

### 5.1 Expression Handling in the Mutator
Crucially, the Mutator engine utilizes the **exact same AST Evaluator** used in Stage 1. This means you have full access to mathematical expressions `(A + B) * C` and ternary logic `X if Y else Z`. However, unlike Stage 1 which evaluates linearly via DAG dependencies, the Mutator evaluates its expressions against the *fully completed base record*. 

Because the base record is finished, the Mutator can reference *any* field on the invoice (e.g., you can mutate the `issue_date` to be mathematically derived from the `payment_account` if you want).

### 5.2 The ActionRegistry Capabilities

The Mutator parses the `action:` key (e.g., `replace`, `modify`, `drop`) and maps it to specific Python Handlers. Below is a robust accounting of the supported actions:

#### 1. The `replace` Handler
Completely overwrites the target field's value. You can provide a hardcoded `value` or an AST `value_computation` string to compute the new value dynamically.
- *Use Case*: Forcing a mathematical error. 
```yaml
mutations:
  - target: payable_amount
    action: replace
    # Accesses the finished base document to inject a specific math error 
    # (calculating 1.5x the tax instead of 1x)
    value_computation: "tax_exclusive + (tax_amount * 1.5)"
  - target: invoice_type
    action: replace
    value: "INVALID_DOCUMENT_TYPE" # Hardcoded override
```

#### 2. The `modify` Handler
The `modify` handler is more elegant than replace. Instead of just overwriting a number, it overrides the original generative `rules` defined in `constraints.yaml` and forces the Faker engine/solver to re-roll a new randomized value that specifically adheres to your anomaly conditions.
- *Use Case*: Creating a temporal violation where the due date is randomly generated to be *before* the issue date.
```yaml
mutations:
  - target: due_date
    action: modify
    rules:
      # Forces the engine to pick a new date strictly in the past
      - "< issue_date" 
```

#### 3. The `drop` Handler
Simply pops the key out of the final JSON dictionary payload. When the Jinja HTML renderer or JSON serializer looks for the key, it will be completely missing.
- *Use Case*: Testing if an AI agent can flag a missing required VAT number.
```yaml
mutations:
  - target: supplier_identifier
    action: drop
```

#### 4. The JSONPath Nested Targeter
Because the base configuration supports natively generated nested lists, the Mutator handles JSONPath bracket/dot notation natively via the `target` parameter string. This gracefully allows intercepting very specific sub-items downstream without corrupting your global layout architecture.
- *Use Case*: Forcing a mathematical mismatch explicitly on the third line item generated.
```yaml
mutations:
  - target: "line_items[2].quantity"
    action: replace
    value: 0
```

### 5.3 Mutator Common Gotchas
> [!CAUTION]
> **No Cascading Re-Computations**: When a mutator alters a field, the engine **does not** cascade changes down the DAG.
> - *Gotcha*: If `line_total` is dependent on `quantity`, and you use the mutator to `replace` the `quantity` to `0`, the `line_total` will remain whatever it originally was in Stage 1!
> - *Why this happens*: This is intentional. Mutating the `quantity` without updating the `line_total` is exactly how you generate a mathematical mismatch anomaly. 
> - *Fix*: If your goal is to change the quantity *and* logically recompute everything down the tree (creating a valid invoice with a different quantity), you should change the base `constraints.yaml`, not the `anomalies.yaml`.

### 5.4 Batch Execution & Anomaly Distributions
When executing the generator pipeline, you must be able to strictly control the dataset volume and the mathematical ratio of cleanly generated invoices versus mutated (anomalous) invoices.

The application orchestrator (`main.py`) exposes runtime CLI arguments to govern this distribution and ensure strict determinism:
- `--count` (e.g., `10000`): The total sum of invoices to generate in the batch.
- `--mutation-rate` (e.g., `0.15`): The percentage (15%) of the total count that should be intercepted by the Mutator Engine. The remaining 85% will pass directly to the I/O layer as pristine "ground truth" Base Records.
- *(Optional)* `--mutation-strategy` (e.g., `uniform`): Determines how the mutated population is evenly distributed across your various test cases defined in `anomalies.yaml`.
- *(Optional)* `--seed` (e.g., `42`): **Crucial for Robustness.** Locks the random state for both the Faker engine and native Python libraries. This ensures that engineers can perfectly reproduce a problematic synthetic dataset during QA debugging.
- *(Optional)* `--preview`: A rapid UX debugging flag that bypasses the bulk I/O Exporters, builds exactly 1 record, and prints the heavily-formatted JSON directly to standard output for immediate YAML iteration feedback.

This allows immediate, command-line scalability to generate a 50,000 document training set with exactly a 10% known error rate for AI benchmarking.

## 6. Flexible Format Output Layer
The `Renderer` layer separates data from presentation.

**Implementation Interface:**
```python
class BaseRenderer(ABC):
    @abstractmethod
    def render(self, record: Dict[str, Any]) -> bytes:
        """Returns the serialized format as raw bytes for the Exporter."""
        pass
```

- **`JSONRenderer`**: Uses `json.dumps()` (handling date serialization) to yield `.json` bytes.
- **`JinjaPDFRenderer`** *(Future Plan)*: Converts structured records into visual PDFs. We have three architectural paths for this:
  - **Option 1: WeasyPrint (Modern & Beautiful)**: Uses modern CSS3 (Flexbox/Grid), yielding premium outputs. Requires some system binaries (`pango`, `cairo`).
  - **Option 2: xhtml2pdf (Fast & Zero System Setup)**: Pure Python, installs instantly with `pip`. Uses older HTML schema (requires table-based layouts, no modern CSS flexbox).
  - **Option 3: ReportLab (Programmatic)**: Pure Python, fast and reliable. Programmatic drawing (requires x/y coordinates), hard to template visually without excessive code.

## 7. Auto-Generative Output Schema (JSON Schema) *(Future Plan)*
To provide a strict, predictable contract for downstream consumers (like databases or AI validation pipelines), the architecture automatically guarantees schema alignment without requiring end-users to manage multiple files.

Because the `constraints.yaml` intrinsically defines every field's data structure via the `type:` key (e.g., `integer`, `string`, `decimal`), the configuration *is* the schema. 

The application exposes a CLI hook (e.g., `python main.py --export-schema`) that natively evaluates the `constraints.yaml` and auto-generates a standardized OpenAPI-compliant JSON Schema document (or Pydantic Model specification). This adheres to the "Don't Repeat Yourself" (DRY) principle—domain experts only maintain the generation logic, while downstream QA testing systems simply ingest the auto-generated JSON schema artifact to validate the final GCS payloads. 

Crucially, by explicitly providing an `example:` key on each YAML field definition, the exported schema automatically populates the OpenAPI `examples` array. This provides downstream developers, QA testers, and mock-servers with instant, realistic reference data without needing to stand up the full Python Faker execution suite.

## 8. Flexible Execution and Storage Targets
The destinations are managed through an `Exporter` interface. 

**Implementation Interface:**
```python
class BaseExporter(ABC):
    @abstractmethod
    def write(self, filename: str, data: bytes) -> None:
        pass
```

**Supported Exporters:**
1. **`LocalFileExporter`**: Writes standard output to a mapped `/output` volume.
2. **`SingleFileBytesExporter`**: Appends streams for writing large JSON Line or JSON Array aggregates sequentially.
3. **`ZipArchiveExporter`** *(Future Plan)*: Keeps an open stream to a `zipfile.ZipFile` in memory and writes directly to members.
4. **`GCSExporter`** *(Future Plan)*: Utilizes the initialized `google-cloud-storage` client to asynchronously upload chunks to `gs://bucket-name/folder/filename`.

## 9. Technology Stack & Setup Experience
The setup experience is specifically designed to be highly standardized, clean, and DRY (Don't Repeat Yourself). The entire application installs natively into a standard Python `venv` via `requirements.txt` or `pyproject.toml` without requiring complex manual OS configurations or binary compilations.

For implementation, the python environment must contain:
- **Core Library & CLI Structure**: Standard Python `argparse`, `importlib`.
- **Validation**: `pydantic` (Strict typing of configs).
- **DAG Generation**: `graphlib.TopologicalSorter` (Python 3.9+ native).
- **Evaluation Engine**: `asteval` (Safe python expression engine), `faker`.
- **Templating Engine**: `jinja2` (HTML formatting).
- **PDF Core**: `weasyprint` (HTML to PDF buffer rasterization).
- **Storage Layer Interfaces**: `google-cloud-storage`, `boto3`.

## 10. End-User Commentary & Gotchas

From the perspective of a domain expert (e.g., a business analyst, QA engineer, or data scientist) configuring this system, the YAML-first approach is incredibly powerful but demands discipline. 

### Commentary on Usability
- **Frictionless Prototyping**: You do not need to wait for a developer sprint to add a new tax bracket or change a currency code. You simply modify `constraints.yaml`, and the system will immediately start yielding datasets with the new schema.
- **Isolating Bad Logic**: Because anomalies are strictly separated into `anomalies.yaml`, you can guarantee that the base dataset is always 100% mathematically flawless before any mutations occur. This makes debugging much easier.

### Common "Gotchas" & Troubleshooting
> [!CAUTION]
> As an end-user, keep these operational gotchas in mind when designing synthetic data rules:

1. **Jinja PDF Layout Breakages**:
   - *Gotcha*: If your YAML constraints start generating very long strings (e.g., `company_name: "Super Long International Corporate Entity GMBH"`), and the visual Jinja template isn't formatted with text-wrapping, the text will overflow the PDF boundaries.
   - *Fix*: Always validate max-lengths in your string generator constraints if relying heavily on PDF rendering.
2. **Hidden Constraints in Nested Fields** (e.g., Line Items):
   - *Gotcha*: When creating nested lists (like `line_items`), ensuring the sum of the line items exactly equals the header `tax_exclusive` total requires careful orchestration.
   - *Fix*: Generate the line items array *first*, then compute the header total dynamically (e.g., `sum(item.line_total for item in line_items)`), rather than generating the header first and trying to divide it into randomized line items.
3. **AST Silent Fails with Missing/Null Data**:
   - *Gotcha*: If a dependency evaluates to `None` (perhaps due to a `fake.optional()` generator), and an AST expression attempts math (e.g., `computed: "discount * 10"`), the parser will throw an execution error.
   - *Fix*: Map out default fallbacks in your ternary logic (e.g., `computed: "(discount if discount is not None else 0) * 10"`).
4. **Faker Locale Contradictions**:
   - *Gotcha*: Declaring `locale: da_DK` in the YAML automatically changes Faker's generative pools (names, zip codes, phone formats). If you simultaneously hardcode a static `currency: "USD"` or `tax_rate: 0.08` while the rest of the document is Danish, it presents a logical contradiction that might break the AI agent's inference training.
   - *Fix*: Visually audit one "Base Record" completely before bulk-generating 10,000 documents to ensure locale harmony.
