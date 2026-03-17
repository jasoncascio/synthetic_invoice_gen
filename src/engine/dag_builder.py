from graphlib import TopologicalSorter, CycleError
from typing import Dict, List
from src.config.models import ConstraintField

class CyclicalDependencyError(Exception):
    pass

def build_execution_order(fields: Dict[str, ConstraintField]) -> List[str]:
    """
    Constructs a directed acyclic graph (DAG) of the constraint fields,
    returning a valid execution order.
    """
    graph = {}
    for field_name, field_def in fields.items():
        # graphlib expects exactly { node: [dependencies that must run before node] }
        graph[field_name] = field_def.dependencies or []
        
    sorter = TopologicalSorter(graph)
    try:
        return list(sorter.static_order())
    except CycleError as e:
        # e.args[1] usually contains the detected cycle sequence
        raise CyclicalDependencyError(
            f"Cycle detected involving fields: {e.args[1]}. A field cannot mathematically depend on itself."
        )
