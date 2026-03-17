from typing import Dict, Any, List
import copy
from src.config.models import AnomaliesConfig
from src.mutator.handlers import DropActionHandler, ReplaceActionHandler, ModifyActionHandler

class ActionRegistry:
    def __init__(self, anomalies_cfg: AnomaliesConfig, engine_ref: Any):
        self.anomalies_cfg = anomalies_cfg
        self.engine_ref = engine_ref
        self.handlers = {
            "drop": DropActionHandler(),
            "replace": ReplaceActionHandler(),
            "modify": ModifyActionHandler()
        }

    def mutate(self, base_record: Dict[str, Any]) -> Dict[str, Any]:
        """
        Creates a deepcopy of the base record and forcefully applies all defined mutations.
        The base record graph logic is NOT cascaded downward, ensuring the anomaly is trapped natively.
        """
        if not self.anomalies_cfg or not self.anomalies_cfg.mutations:
            return base_record
            
        mutated = copy.deepcopy(base_record)
        mutated["_scenario_label"] = "mutated"
        
        for rule in self.anomalies_cfg.mutations:
            handler = self.handlers.get(rule.action)
            if not handler:
                raise ValueError(f"Unknown mutator action type: {rule.action}")
            handler.apply(rule, mutated, self.engine_ref)
            
        return mutated
