from __future__ import annotations

from pathlib import Path

from workflow_state_machine.analysis import (
    can_finish,
    dead_ends,
    error_count,
    reachable,
    reachable_terminals,
    self_loops,
    terminal_exits,
    transition_labels,
    unreachable,
    validate,
)
from workflow_state_machine.machine import parse_machine

EXAMPLES = Path(__file__).resolve().parent.parent / "examples"
ORDER = parse_machine((EXAMPLES / "order-fulfilment.json").read_text(encoding="utf-8"))
LEAKY = parse_machine((EXAMPLES / "leaky-process.json").read_text(encoding="utf-8"))


def codes(machine) -> set[str]:
    return {problem.code for problem in validate(machine)}


def test_reachability_of_the_sound_machine() -> None:
    assert reachable(ORDER) == {
        "created",
        "paid",
        "packed",
        "shipped",
        "on_hold",
        "delivered",
        "cancelled",
    }
    assert unreachable(ORDER) == []
    assert can_finish(ORDER) is True


def test_sound_machine_has_no_problems() -> None:
    assert validate(ORDER) == []


def test_leaky_machine_problems() -> None:
    problems = validate(LEAKY)
    found = {problem.code for problem in problems}
    assert found == {"dead-end", "unreachable-state", "terminal-with-exit", "self-loop", "no-cancel-path"}
    assert error_count(problems) == 2


def test_problems_sorted_by_severity() -> None:
    severities = [problem.severity for problem in validate(LEAKY)]
    assert severities == ["error", "error", "warning", "warning", "note", "note"]


def test_dead_ends_and_terminal_exits() -> None:
    assert dead_ends(LEAKY) == ["archived", "orphan"]
    assert terminal_exits(LEAKY) == ["approved"]
    assert dead_ends(ORDER) == []


def test_unreachable_only_lists_declared_states() -> None:
    assert unreachable(LEAKY) == ["orphan"]


def test_self_loops() -> None:
    assert self_loops(LEAKY) == ["review:retry"]
    assert self_loops(ORDER) == []


def test_reachable_terminals() -> None:
    assert reachable_terminals(ORDER) == ["delivered", "cancelled"]
    assert reachable_terminals(LEAKY) == ["approved"]


def test_machine_without_terminals() -> None:
    machine = parse_machine(
        {
            "initial": "a",
            "states": [{"name": "a"}, {"name": "b"}],
            "transitions": [{"from": "a", "event": "go", "to": "b"}, {"from": "b", "event": "cancel", "to": "a"}],
        }
    )
    found = codes(machine)
    assert "no-terminal" in found
    assert can_finish(machine) is False


def test_machine_without_transitions() -> None:
    machine = parse_machine({"initial": "a", "states": [{"name": "a", "terminal": True}]})
    assert "no-transitions" in codes(machine)


def test_unreachable_terminal_is_reported() -> None:
    machine = parse_machine(
        {
            "initial": "a",
            "states": [{"name": "a", "terminal": True}, {"name": "island", "terminal": True}],
            "transitions": [{"from": "a", "event": "cancel", "to": "a"}],
        }
    )
    problems = {problem.code: problem for problem in validate(machine)}
    assert "unreachable-terminal" in problems
    assert "island" in problems["unreachable-terminal"].message


def test_terminal_unreachable_error() -> None:
    machine = parse_machine(
        {
            "initial": "a",
            "states": [{"name": "a"}, {"name": "b", "terminal": True}],
            "transitions": [{"from": "a", "event": "cancel", "to": "a"}],
        }
    )
    assert "terminal-unreachable" in codes(machine)


def test_transition_labels() -> None:
    labels = transition_labels(ORDER)
    assert labels[0] == "created-pay"
    assert len(labels) == len(ORDER.transitions)


def test_problem_dict() -> None:
    payload = validate(LEAKY)[0].as_dict()
    assert set(payload) == {"code", "severity", "message"}
