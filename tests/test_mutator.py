import pytest
from src.mutator.handlers import resolve_target, DropActionHandler, ReplaceActionHandler
from src.config.models import MutationRule

def test_resolve_target_flat():
    context = {"x": 10}
    parent, key = resolve_target("x", context)
    assert parent == context
    assert key == "x"

def test_resolve_target_nested_object():
    context = {"user": {"name": "Alice"}}
    parent, key = resolve_target("user.name", context)
    assert parent == context["user"]
    assert key == "name"

def test_resolve_target_nested_array():
    context = {"items": [{"name": "item1"}, {"name": "item2"}]}
    parent, key = resolve_target("items[1].name", context)
    assert parent == context["items"][1]
    assert key == "name"

def test_drop_handler():
    context = {"items": ["a", "b", "c"]}
    rule = MutationRule(target="items[1]", action="drop")
    handler = DropActionHandler()
    handler.apply(rule, context, None)
    assert context["items"] == ["a", "c"]

def test_replace_handler_value():
    context = {"x": 10}
    rule = MutationRule(target="x", action="replace", value=20)
    handler = ReplaceActionHandler()
    handler.apply(rule, context, None)
    assert context["x"] == 20

def test_replace_handler_computation():
    context = {"x": 10, "y": 5}
    rule = MutationRule(target="x", action="replace", value_computation="y * 3")
    handler = ReplaceActionHandler()
    handler.apply(rule, context, None)
    assert context["x"] == 15
