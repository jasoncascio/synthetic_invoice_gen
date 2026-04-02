import pytest
from pydantic import ValidationError
from src.config.models import ConstraintField

def test_config_validation_exclusivity():
    with pytest.raises(ValidationError):
        ConstraintField(
            type="decimal",
            generator="random.uniform",
            computed="quantity * 10"
        )

def test_config_validation_static_requires_value():
    with pytest.raises(ValidationError):
        ConstraintField(type="static")

def test_config_validation_array_requires_count():
    with pytest.raises(ValidationError):
        ConstraintField(type="array", schema_def={"x": ConstraintField(type="string")})
