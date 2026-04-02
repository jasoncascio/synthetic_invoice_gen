import pytest
from src.config.models import ConstraintsConfig, ConstraintField, AnomaliesConfig, MutationRule

@pytest.fixture
def sample_constraints():
    return ConstraintsConfig(
        fields={
            "quantity": ConstraintField(
                type="integer", 
                generator="random.randint", 
                generator_args={"a": 1, "b": 10}
            ),
            "unit_price": ConstraintField(
                type="decimal", 
                generator="random.uniform", 
                generator_args={"a": 1.0, "b": 10.0}
            ),
            "total": ConstraintField(
                type="decimal",
                dependencies=["quantity", "unit_price"],
                computed="round(quantity * unit_price, 2)"
            )
        }
    )

@pytest.fixture
def sample_anomalies():
    return AnomaliesConfig(
        mutations=[
            MutationRule(target="quantity", action="replace", value=-5)
        ]
    )
