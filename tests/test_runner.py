from __future__ import annotations

from pathlib import Path

import pytest

from workflow_state_machine.machine import parse_machine
from workflow_state_machine.runner import (
    reachable_states,
    run,
    shortest_path,
    unexplored_events,
)

EXAMPLES = Path(__file__).resolve().parent.parent / "examples"
ORDER = parse_machine((EXAMPLES / "order-fulfilment.json").read_text(encoding="utf-8"))


def test_successful_run() -> None:
    result = run(ORDER, ["pay", "pack", "ship", "deliver"])
    assert result.ok is True
    assert result.final_state == "delivered"
    assert result.terminal is True
    assert result.path == ["created", "paid", "packed", "shipped", "delivered"]
    assert [step.target for step in result.steps] == ["paid", "packed", "shipped", "delivered"]


def test_empty_run_stays_put() -> None:
    result = run(ORDER, [])
    assert result.ok is True
    assert result.final_state == "created"
    assert result.terminal is False
    assert result.steps == []


def test_rejection_reports_available_events() -> None:
    result = run(ORDER, ["pack"])
    assert result.ok is False
    assert result.rejection is not None
    assert result.rejection.event == "pack"
    assert result.rejection.state == "created"
    assert result.rejection.available == ("pay", "cancel")
    assert result.final_state == "created"


def test_run_stops_at_the_first_rejection() -> None:
    result = run(ORDER, ["pay", "nonsense", "pack"])
    assert len(result.steps) == 1
    assert result.rejection is not None
    assert result.rejection.index == 2
    assert result.final_state == "paid"


def test_run_from_another_state() -> None:
    result = run(ORDER, ["release", "pack"], start="on_hold")
    assert result.ok is True
    assert result.final_state == "packed"
    assert result.start == "on_hold"


def test_unknown_start_state() -> None:
    with pytest.raises(ValueError, match="unknown start state"):
        run(ORDER, [], start="nowhere")


def test_coverage_counts_used_transitions() -> None:
    result = run(ORDER, ["pay", "pack", "ship", "deliver"])
    assert result.coverage.total == 9
    assert result.coverage.taken == ("created-pay", "paid-pack", "packed-ship", "shipped-deliver")
    assert round(result.coverage.percent) == 44


def test_coverage_of_an_empty_machine_run() -> None:
    result = run(ORDER, [])
    assert result.coverage.percent == 0.0


def test_run_as_dict() -> None:
    payload = run(ORDER, ["pay"]).as_dict()
    assert payload["final_state"] == "paid"
    assert payload["steps"][0] == {"index": 1, "event": "pay", "from": "created", "to": "paid"}
    assert payload["rejection"] is None
    assert payload["path"] == ["created", "paid"]


def test_shortest_path_to_delivered() -> None:
    route = shortest_path(ORDER, "delivered")
    assert route is not None
    assert route.events == ("pay", "pack", "ship", "deliver")
    assert route.length == 4
    assert route.states[-1] == "delivered"


def test_shortest_path_prefers_fewer_events() -> None:
    route = shortest_path(ORDER, "cancelled")
    assert route is not None
    assert route.events == ("cancel",)


def test_shortest_path_to_self() -> None:
    route = shortest_path(ORDER, "created")
    assert route is not None
    assert route.events == ()
    assert route.as_dict() == {"events": [], "states": ["created"], "length": 0}


def test_shortest_path_from_a_state() -> None:
    route = shortest_path(ORDER, "delivered", start="packed")
    assert route is not None
    assert route.events == ("ship", "deliver")


def test_shortest_path_unreachable_returns_none() -> None:
    machine = parse_machine(
        {
            "initial": "a",
            "states": [{"name": "a"}, {"name": "island", "terminal": True}],
            "transitions": [{"from": "a", "event": "cancel", "to": "a"}],
        }
    )
    assert shortest_path(machine, "island") is None


def test_shortest_path_validates_states() -> None:
    with pytest.raises(ValueError, match="unknown target"):
        shortest_path(ORDER, "nope")
    with pytest.raises(ValueError, match="unknown start"):
        shortest_path(ORDER, "delivered", start="nope")


def test_reachable_states_are_breadth_first() -> None:
    order = reachable_states(ORDER)
    assert order[0] == "created"
    assert set(order) == set(ORDER.state_names)
    assert order.index("paid") < order.index("packed") < order.index("shipped")


def test_unexplored_events() -> None:
    missing = unexplored_events(ORDER, run(ORDER, ["pay", "pack"]))
    assert missing["created"] == ["cancel"]
    assert missing["paid"] == ["hold", "refund"]
    assert "shipped" in missing
