from abc import ABC, abstractmethod
from typing import Dict, Any

class SyntheticGeneratorPlugin(ABC):
    """
    Abstract base class for custom generator plugins.
    Implement the generate() method to yield custom pythonic values into the context record.
    """
    @abstractmethod
    def generate(self, context_record: Dict[str, Any]) -> Any:
        pass
