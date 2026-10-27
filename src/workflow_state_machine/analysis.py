"""Reachability, dead ends and coverage checks over a machine."""

from __future__ import annotations

from dataclasses import dataclass

from workflow_state_machine.machine import Machine

SEVERITIES = ("error", "warning", "note")
SEVERITY_ORDER = {severity: index for index, severity in enumerate(SEVERITIES)}


@dataclass(frozen=True)
class Problem:
    code: str
    severity: str
    message: str

    def as_dict(self) -> dict:
        return {"code": self.code, "severity": self.severity, "message": self.message}


def reachable(machine: Machine) -> set[str]:
    """States you can actually get to, starting from the initial state."""
    seen = {machine.initial}
    queue = [machine.initial]
    while queue:
        current = queue.pop(0)
        for transition in machine.outgoing(current):
            if transition.target not in seen:
                seen.add(transition.target)
                queue.append(transition.target)
    return seen


def unreachable(machine: Machine) -> list[str]:
    seen = reachable(machine)
    return [state.name for state in machine.states if state.name not in seen]


def dead_ends(machine: Machine) -> list[str]:
    """Non-terminal states with no way out: the workflow stops without finishing."""
    return [state.name for state in machine.states if not state.terminal and not machine.outgoing(state.name)]


def terminal_exits(machine: Machine) -> list[str]:
    """Terminal states that still have outgoing transitions, which makes 'done' ambiguous."""
    return [state.name for state in machine.states if state.terminal and machine.outgoing(state.name)]


def self_loops(machine: Machine) -> list[str]:
    return [
        f"{transition.source}:{transition.event}"
        for transition in machine.transitions
        if transition.source == transition.target
    ]


def reachable_terminals(machine: Machine) -> list[str]:
    seen = reachable(machine)
    return [name for name in machine.terminals if name in seen]


def can_finish(machine: Machine) -> bool:
    return bool(reachable_terminals(machine))


def validate(machine: Machine) -> list[Problem]:
    """Every problem worth reporting, ordered by severity."""
    problems: list[Problem] = []

    if not machine.transitions:
        problems.append(Problem("no-transitions", "error", "the machine has no transitions at all"))

    for name in unreachable(machine):
        problems.append(
            Problem("unreachable-state", "warning", f"state '{name}' cannot be reached from '{machine.initial}'")
        )

    for name in dead_ends(machine):
        problems.append(
            Problem("dead-end", "error", f"state '{name}' is not terminal but has no outgoing transition")
        )

    for name in terminal_exits(machine):
        problems.append(
            Problem("terminal-with-exit", "warning", f"terminal state '{name}' still has outgoing transitions")
        )

    for entry in self_loops(machine):
        problems.append(Problem("self-loop", "note", f"self transition '{entry}' never changes state"))

    if not machine.terminals:
        problems.append(Problem("no-terminal", "warning", "no state is marked terminal"))
    elif not can_finish(machine):
        problems.append(
            Problem("terminal-unreachable", "error", "no terminal state can be reached from the initial state")
        )

    unreachable_terms = [name for name in machine.terminals if name not in reachable(machine)]
    if unreachable_terms and can_finish(machine):
        problems.append(
            Problem(
                "unreachable-terminal",
                "warning",
                f"terminal state(s) never reached: {', '.join(unreachable_terms)}",
            )
        )

    if not any("cancel" in transition.event for transition in machine.transitions):
        problems.append(Problem("no-cancel-path", "note", "no transition uses a 'cancel' style event"))

    problems.sort(key=lambda problem: SEVERITY_ORDER[problem.severity])
    return problems


def error_count(problems: list[Problem]) -> int:
    return sum(1 for problem in problems if problem.severity == "error")


@dataclass(frozen=True)
class Coverage:
    total: int
    taken: tuple[str, ...]

    @property
    def percent(self) -> float:
        if not self.total:
            return 0.0
        return len(self.taken) / self.total * 100.0

    def as_dict(self) -> dict:
        return {"total": self.total, "taken": list(self.taken), "percent": round(self.percent, 1)}


def transition_labels(machine: Machine) -> list[str]:
    return [f"{transition.source}-{transition.event}" for transition in machine.transitions]
