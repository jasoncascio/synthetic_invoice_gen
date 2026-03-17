from __future__ import annotations
from typing import Any, Dict, List, Literal, Optional
from pydantic import BaseModel, Field, model_validator

class ConstraintField(BaseModel):
    type: Literal["string", "integer", "decimal", "date", "boolean", "static", "array", "object"]
    value: Optional[Any] = None
    example: Optional[Any] = None
    dependencies: Optional[List[str]] = Field(default_factory=list)
    generator: Optional[str] = None
    generator_args: Optional[Dict[str, Any]] = None
    rules: Optional[List[str]] = None
    computed: Optional[str] = None
    plugin: Optional[str] = None
    
    # Native Structural Types
    count_expr: Optional[str] = None
    schema_def: Optional[Dict[str, 'ConstraintField']] = Field(default=None, alias="schema")

    @model_validator(mode="after")
    def validate_exclusivity(self) -> "ConstraintField":
        strategies = [
            self.type == "static",
            bool(self.generator),
            bool(self.computed),
            bool(self.plugin),
            self.type in ("array", "object")
        ]
        if sum(strategies) > 1:
            raise ValueError(
                "A field cannot simultaneously use multiple generation strategies (static, generator, computed, plugin, array/object schema). Choose one."
            )
        if self.type == "static" and self.value is None:
            raise ValueError("A 'static' field must provide a 'value'.")
        if self.computed and not self.dependencies:
            raise ValueError("A 'computed' field usually requires dependencies to be declared.")
        if self.type in ("array", "object") and not self.schema_def:
            raise ValueError(f"An '{self.type}' field must provide a 'schema' definition containing its nested fields.")
        if self.type == "array" and not self.count_expr:
            raise ValueError("An 'array' field must specify 'count_expr' (e.g., 'random.randint(1, 5)').")
        return self

# Explicitly rebuild to resolve forward references for Dict[str, 'ConstraintField']
ConstraintField.model_rebuild()

class ConstraintsConfig(BaseModel):
    locale: str = "en_US"
    fields: Dict[str, ConstraintField]

class MutationRule(BaseModel):
    target: str
    action: Literal["replace", "modify", "drop"]
    value: Optional[Any] = None
    value_computation: Optional[str] = None
    rules: Optional[List[str]] = None

    @model_validator(mode="after")
    def validate_action_args(self) -> "MutationRule":
        if self.action == "replace" and self.value is None and self.value_computation is None:
            raise ValueError("Action 'replace' requires either 'value' or 'value_computation'.")
        if self.action == "modify" and not self.rules:
            raise ValueError("Action 'modify' requires 'rules'.")
        return self

class AnomaliesConfig(BaseModel):
    mutations: List[MutationRule]
