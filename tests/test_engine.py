import pytest
from src.engine.evaluator import ASTEvaluator, MissingReferenceError, ExpressionSyntaxError
from src.engine.dag_builder import build_execution_order, CyclicalDependencyError
from src.config.models import ConstraintField

def test_ast_evaluator_simple():
    evaluator = ASTEvaluator({})
    assert evaluator.evaluate("1 + 1") == 2

def test_ast_evaluator_context():
    evaluator = ASTEvaluator({"x": 10, "y": 5})
    assert evaluator.evaluate("x * y") == 50

def test_ast_evaluator_missing_ref():
    evaluator = ASTEvaluator({})
    with pytest.raises(MissingReferenceError):
        evaluator.evaluate("x + y")

def test_ast_evaluator_syntax_error():
    evaluator = ASTEvaluator({})
    with pytest.raises(ExpressionSyntaxError):
        evaluator.evaluate("1 + ")

def test_dag_builder_valid():
    fields = {
        "a": ConstraintField(type="string"),
        "b": ConstraintField(type="string", dependencies=["a"]),
        "c": ConstraintField(type="string", dependencies=["b"])
    }
    order = build_execution_order(fields)
    assert order == ["a", "b", "c"]

def test_dag_builder_cycle():
    fields = {
        "a": ConstraintField(type="string", dependencies=["b"]),
        "b": ConstraintField(type="string", dependencies=["a"])
    }
    with pytest.raises(CyclicalDependencyError):
        build_execution_order(fields)
