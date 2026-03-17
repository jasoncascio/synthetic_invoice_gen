import random
import importlib
import uuid
from typing import Dict, Any, Optional
from faker import Faker
from src.config.models import ConstraintsConfig, ConstraintField
from src.engine.evaluator import ASTEvaluator
from src.engine.dag_builder import build_execution_order

class ConstraintSatisfactionError(Exception):
    pass

class PluginResolutionError(Exception):
    pass

class GeneratorEngine:
    def __init__(self, config: ConstraintsConfig, value_spaces: Dict[str, list], seed: Optional[int] = None):
        self.config = config
        self.value_spaces = value_spaces
        self.faker = Faker(config.locale)
        
        if seed is not None:
            self.faker.seed_instance(seed)
            random.seed(seed)
            
        self.execution_order = build_execution_order(self.config.fields)
        self.max_retries = 500

    def load_plugin(self, plugin_path: str):
        try:
            module_name, class_name = plugin_path.rsplit('.', 1)
            module = importlib.import_module(module_name)
            plugin_class = getattr(module, class_name)
            return plugin_class()
        except Exception as e:
            raise PluginResolutionError(f"Failed to load plugin {plugin_path}: {str(e)}")

    def _execute_generator(self, field_def: ConstraintField) -> Any:
        gen_path = field_def.generator
        args = field_def.generator_args or {}
        
        if gen_path == "value_space.random":
            space_key = args.get("space")
            fallback_path = args.get("fallback")
            if space_key and space_key in self.value_spaces and self.value_spaces[space_key]:
                return random.choice(self.value_spaces[space_key])
            elif fallback_path:
                gen_path = fallback_path
            else:
                raise KeyError(f"Value space '{space_key}' missing and no fallback provided.")
                
        if gen_path.startswith("random."):
            method_name = gen_path.split(".")[1]
            return getattr(random, method_name)(**args)
            
        if gen_path.startswith("uuid."):
            method_name = gen_path.split(".")[1]
            return str(getattr(uuid, method_name)(**args))

        if gen_path.startswith("fake."):
            method_name = gen_path.split(".")[1]
            return getattr(self.faker, method_name)(**args)
            
        raise ValueError(f"Unknown generator namespace: {gen_path}")

    def _satisfies_rules(self, value: Any, rules: list, context_record: Dict[str, Any]) -> bool:
        if not rules:
            return True
        evaluator = ASTEvaluator(context_record)
        
        for rule in rules:
            rule_clean = rule.strip()
            if rule_clean.startswith(">="):
                limit = evaluator.evaluate(rule_clean.replace(">=", "", 1).strip())
                if not (value >= limit): return False
            elif rule_clean.startswith("<="):
                limit = evaluator.evaluate(rule_clean.replace("<=", "", 1).strip())
                if not (value <= limit): return False
            elif rule_clean.startswith(">"):
                limit = evaluator.evaluate(rule_clean.replace(">", "", 1).strip())
                if not (value > limit): return False
            elif rule_clean.startswith("<"):
                limit = evaluator.evaluate(rule_clean.replace("<", "", 1).strip())
                if not (value < limit): return False
            elif rule_clean.startswith("=="):
                limit = evaluator.evaluate(rule_clean.replace("==", "", 1).strip())
                if not (value == limit): return False
            elif rule_clean.startswith("!="):
                limit = evaluator.evaluate(rule_clean.replace("!=", "", 1).strip())
                if not (value != limit): return False
            elif " in " in rule_clean:
                _, sequence_str = rule_clean.split(" in ", 1)
                sequence = evaluator.evaluate(sequence_str.strip())
                if value not in sequence: return False
        return True

    def _generate_field_value(self, field_name: str, field_def: ConstraintField, context_record: Dict[str, Any]) -> Any:
        """ Recursive generator capable of resolving deeply nested objects and arrays. """
        if field_def.type == "static":
            return field_def.value
            
        elif field_def.computed:
            evaluator = ASTEvaluator(context_record)
            return evaluator.evaluate(field_def.computed)
            
        elif field_def.plugin:
            plugin = self.load_plugin(field_def.plugin)
            return plugin.generate(context_record)
            
        elif field_def.type == "array":
            count_evaluator = ASTEvaluator(context_record)
            count = int(count_evaluator.evaluate(field_def.count_expr))
            
            inner_order = build_execution_order(field_def.schema_def)
            result_list = []
            
            for _ in range(count):
                local_context = {**context_record} 
                item_dict = {}
                for inner_field_name in inner_order:
                    inner_def = field_def.schema_def[inner_field_name]
                    val = self._generate_field_value(inner_field_name, inner_def, local_context)
                    local_context[inner_field_name] = val
                    item_dict[inner_field_name] = val
                result_list.append(item_dict)
            return result_list
            
        elif field_def.type == "object":
            inner_order = build_execution_order(field_def.schema_def)
            local_context = {**context_record}
            item_dict = {}
            for inner_field_name in inner_order:
                inner_def = field_def.schema_def[inner_field_name]
                val = self._generate_field_value(inner_field_name, inner_def, local_context)
                local_context[inner_field_name] = val
                item_dict[inner_field_name] = val
            return item_dict
            
        elif field_def.generator:
            attempts = 0
            while attempts < self.max_retries:
                cand = self._execute_generator(field_def)
                if self._satisfies_rules(cand, field_def.rules or [], context_record):
                    return cand
                attempts += 1
            raise ConstraintSatisfactionError(f"Failed to generate '{field_name}' after {self.max_retries} attempts.")

    def generate_record(self, batch_id: str, seq_num: int) -> Dict[str, Any]:
        context = {
            "_batch_id": batch_id,
            "_sequence_num": seq_num
        }
        
        for field_name in self.execution_order:
            field_def = self.config.fields[field_name]
            generated_value = self._generate_field_value(field_name, field_def, context)
            context[field_name] = generated_value
            
        return context
