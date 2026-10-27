from __future__ import annotations

import json
from pathlib import Path

import pytest

from workflow_state_machine.machine import MachineError, parse_machine

EXAMPLES = Path(__file__).resolve().parent.parent / "examples"

SIMPLE = {
    "name": "Deploy",
    "initial": "draft",
    "states": [
        {"name": "draft"},
        {"name": "review"},
        {"name": "live", "terminal": True},
    ],
    "transitions": [
        {"from": "draft", "event": "submit", "to": "review"},
        {"from": "review", "event": "approve", "to": "live"},
    ],
}


def test_parses_states_and_transitions() -> None:
    machine = parse_machine(SIMPLE)
    assert machine.name == "Deploy"
    assert machine.initial == "draft"
    assert machine.state_names == ["draft", "review", "live"]
    assert machine.terminals == ["live"]
    assert len(machine.transitions) == 2


def test_accepts_a_json_string() -> None:
    assert parse_machine(json.dumps(SIMPLE)).initial == "draft"


def test_default_name() -> None:
    payload = dict(SIMPLE)
    payload.pop("name")
    assert parse_machine(payload).name == "State machine"


def test_events_and_outgoing_helpers() -> None:
    machine = parse_machine(SIMPLE)
    assert machine.events_from("draft") == ["submit"]
    assert machine.outgoing("review")[0].target == "live"
    assert machine.events_from("live") == []
    assert machine.is_terminal("live") is True
    assert machine.is_terminal("draft") is False
    assert machine.state("nope") is None


def test_transitions_are_optional() -> None:
    machine = parse_machine({"initial": "done", "states": [{"name": "done", "terminal": True}]})
    assert machine.transitions == []


@pytest.mark.parametrize(
    "payload",
    [
        "{broken",
        [],
        {"initial": "a"},
        {"initial": "a", "states": []},
        {"initial": "zzz", "states": [{"name": "a"}]},
        {"initial": "a", "states": [{"name": "a"}, {"name": "a"}]},
        {"initial": "a", "states": [{"name": "a", "terminal": "yes"}]},
        {"initial": "a", "states": [{"name": "a"}], "transitions": {"from": "a"}},
        {"initial": "a", "states": [{"name": "a"}], "transitions": [{"from": "a", "event": "go", "to": "b"}]},
        {"initial": "a", "states": [{"name": "a"}], "transitions": [{"from": "z", "event": "go", "to": "a"}]},
        {"initial": "a", "states": [{"name": "a", "description": 5}]},
        {"initial": "a", "states": [{"name": ""}]},
        {"initial": "a", "states": [{"name": "a"}], "name": 5},
    ],
)
def test_invalid_definitions(payload) -> None:
    with pytest.raises(MachineError):
        parse_machine(payload)


def test_ambiguous_event_is_fatal() -> None:
    payload = {
        "initial": "a",
        "states": [{"name": "a"}, {"name": "b"}, {"name": "c"}],
        "transitions": [
            {"from": "a", "event": "go", "to": "b"},
            {"from": "a", "event": "go", "to": "c"},
        ],
    }
    with pytest.raises(MachineError, match="two transitions for event"):
        parse_machine(payload)


def test_example_machine_loads() -> None:
    machine = parse_machine((EXAMPLES / "order-fulfilment.json").read_text(encoding="utf-8"))
    assert machine.name == "Order fulfilment"
    assert len(machine.states) == 7
    assert machine.terminals == ["delivered", "cancelled"]
    assert machine.events_from("paid") == ["pack", "hold", "refund"]


def test_state_and_transition_dicts() -> None:
    machine = parse_machine(SIMPLE)
    assert machine.states[2].as_dict() == {"name": "live", "terminal": True, "description": ""}
    assert machine.transitions[0].as_dict()["event"] == "submit"
