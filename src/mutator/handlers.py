import re
from abc import ABC, abstractmethod
from typing import Dict, Any, Tuple
from src.config.models import MutationRule
from src.engine.evaluator import ASTEvaluator

def resolve_target(path: str, context_record: Dict[str, Any]) -> Tuple[Any, Any]:
    """ Parses a target path like `line_items[0].quantity` and returns (parent_object, key_to_overwrite) """
    raw_segments = re.findall(r'[^\[\]\.]+', path)
    segments = []
    for s in raw_segments:
        if s.isdigit():
            segments.append(int(s))
        else:
            segments.append(s)

    current = context_record
    for seg in segments[:-1]:
        current = current[seg] 
        
    return current, segments[-1]


class BaseActionHandler(ABC):
    @abstractmethod
    def apply(self, rule: MutationRule, context_record: Dict[str, Any], engine_ref: Any) -> None:
        pass


class DropActionHandler(BaseActionHandler):
    def apply(self, rule: MutationRule, context_record: Dict[str, Any], engine_ref: Any) -> None:
        try:
            parent, key = resolve_target(rule.target, context_record)
            if isinstance(parent, list) and isinstance(key, int):
                parent.pop(key)
            elif key in parent:
                del parent[key]
        except (KeyError, IndexError, TypeError):
            pass  # Safely ignore missing deep paths on Drops


class ReplaceActionHandler(BaseActionHandler):
    def apply(self, rule: MutationRule, context_record: Dict[str, Any], engine_ref: Any) -> None:
        try:
            parent, key = resolve_target(rule.target, context_record)
            if rule.value_computation:
                evaluator = ASTEvaluator(context_record)
                parent[key] = evaluator.evaluate(rule.value_computation)
            elif rule.value is not None:
                parent[key] = rule.value
        except (KeyError, IndexError, TypeError):
            pass


class ModifyActionHandler(BaseActionHandler):
    def apply(self, rule: MutationRule, context_record: Dict[str, Any], engine_ref: Any) -> None:
        try:
            parent, key = resolve_target(rule.target, context_record)
        except (KeyError, IndexError, TypeError):
            raise KeyError(f"Cannot resolve deeply targetted modify mutation path: {rule.target}")
            
        str_segments = [s for s in re.findall(r'[^\[\]\.]+', rule.target) if not s.isdigit()]
        
        field_def = engine_ref.config.fields.get(str_segments[0])
        for s in str_segments[1:]:
            if field_def and field_def.schema_def:
                field_def = field_def.schema_def.get(s)
            else:
                field_def = None
                
        if not field_def:
             raise KeyError(f"Cannot map modify mutation field definition from path {rule.target}")
             
        attempts = 0
        success = False
        while attempts < engine_ref.max_retries:
            cand = engine_ref._execute_generator(field_def)
            if engine_ref._satisfies_rules(cand, rule.rules or [], context_record):
                parent[key] = cand
                success = True
                break
            attempts += 1
            
        if not success:
            raise RuntimeError(f"Modify Handler failed to re-roll {rule.target} after {engine_ref.max_retries} attempts.")
