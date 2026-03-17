import yaml
from typing import Dict, Any, Optional
from .models import ConstraintsConfig, AnomaliesConfig

def load_yaml(filepath: str) -> Dict[str, Any]:
    with open(filepath, 'r') as f:
        return yaml.safe_load(f)

def load_constraints(filepath: str) -> ConstraintsConfig:
    data = load_yaml(filepath)
    return ConstraintsConfig(**data)

def load_anomalies(filepath: str) -> AnomaliesConfig:
    data = load_yaml(filepath)
    return AnomaliesConfig(**data)

def load_value_spaces(filepath: Optional[str]) -> Dict[str, list]:
    if not filepath:
        return {}
    try:
        return load_yaml(filepath)
    except FileNotFoundError:
        return {}
