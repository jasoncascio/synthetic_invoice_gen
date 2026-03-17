import json
import datetime
from decimal import Decimal
from abc import ABC, abstractmethod
from typing import Dict, Any

class CustomEncoder(json.JSONEncoder):
    """ Correctly serializes Faker native dates and AST Math Decimals into raw JSON """
    def default(self, obj):
        if isinstance(obj, (datetime.date, datetime.datetime)):
            return obj.isoformat()
        if isinstance(obj, Decimal):
            return str(obj)
        return super().default(obj)

class BaseRenderer(ABC):
    @abstractmethod
    def render(self, record: Dict[str, Any]) -> bytes:
        pass

class JSONRenderer(BaseRenderer):
    def render(self, record: Dict[str, Any]) -> bytes:
        # Standard formatted JSON structure
        return json.dumps(record, cls=CustomEncoder, indent=2).encode('utf-8')

class JSONLRowRenderer(BaseRenderer):
    def render(self, record: Dict[str, Any]) -> bytes:
        # Tightly packed sequential row formatting for BigQuery data lakes
        return (json.dumps(record, cls=CustomEncoder) + '\n').encode('utf-8')
