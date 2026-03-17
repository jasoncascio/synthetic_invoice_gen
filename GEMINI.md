# General Disposition & Project Philosophy
1. **Reasonable & Doable**: Keep implementations pragmatic, clean, and native. Avoid over-engineering "crazy" monolithic solutions when standard Python methods suffice.
2. **Clean & DRY Setup**: The developer experience must be frictionless. Rely on standard Python `requirements.txt`/`venv` patterns and eliminate complex manual system configurations.
3. **Decoupled Architecture**: Strictly enforce boundaries between data config (`Pydantic`), core generator math (DAG + AST), manipulation logic (`Mutator`), and output presentation (`I/O`). Do not blend these abstract layers.

# Code Quality & Error Handling Rules
1. **Actionable Exceptions**: NEVER throw generic or raw Python tracebacks to the end-user. All exceptions must be explicitly caught and mapped to named, domain-specific errors (e.g., `CyclicalDependencyError`). Most importantly, an exception log MUST include an explicit, readable suggestion on how the user can immediately fix their configuration file.
2. **Strict Validation Before Execution**: Use `pydantic` heavily using `@model_validator` properties to validate all configuration edges at application boot. Prevent the engine from ever attempting to execute if mutually exclusive rules exist.
3. **Deterministic Testing**: If a module involves randomization (like `Faker` or `random`), ensure the layer natively supports `--seed` arguments for flawless QA reproducibility.
4. **Native Extensibility**: Whenever designing complex data structures (like nested JSON Array schemas), natively engineer recursive support rather than forcing users to rely on messy external `Plugin` scripts.

# Workflow & Communication Execution
1. **Phase-by-Phase**: Execute gigantic architectures in incremental, testable phases (e.g., "Validate Math and Base Logic first, defer PDF Rendering until later"). Build the core cleanly before polishing the visual outputs.
2. **Schema-Driven Outputs**: When introducing new data structures, ensure they automatically align with downstream consumers by maintaining clean YAML types that instantly compile into OpenAPI/JSON Schemas.
