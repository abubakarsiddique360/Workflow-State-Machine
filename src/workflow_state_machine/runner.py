"""Simulate event sequences and find the shortest route between states."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field

from workflow_state_machine.analysis import Coverage, transition_labels
from workflow_state_machine.machine import Machine


@dataclass(frozen=True)
class Step:
    index: int
    event: str
    source: str
    target: str

    def as_dict(self) -> dict:
        return {"index": self.index, "event": self.event, "from": self.source, "to": self.target}


@dataclass(frozen=True)
class Rejection:
    index: int
    event: str
    state: str
    available: tuple[str, ...]

    def as_dict(self) -> dict:
        return {
            "index": self.index,
            "event": self.event,
            "state": self.state,
            "available": list(self.available),
        }


@dataclass
class Run:
    machine: Machine
    start: str
    events: tuple[str, ...]
    steps: list[Step] = field(default_factory=list)
    rejection: Rejection | None = None

    @property
    def ok(self) -> bool:
        return self.rejection is None

    @property
    def final_state(self) -> str:
        return self.steps[-1].target if self.steps else self.start

    @property
    def terminal(self) -> bool:
        return self.machine.is_terminal(self.final_state)

    @property
    def coverage(self) -> Coverage:
        labels = transition_labels(self.machine)
        taken = {f"{step.source}-{step.event}" for step in self.steps}
        return Coverage(total=len(labels), taken=tuple(label for label in labels if label in taken))

    @property
    def path(self) -> list[str]:
        return [self.start, *(step.target for step in self.steps)]

    def as_dict(self) -> dict:
        return {
            "start": self.start,
            "events": list(self.events),
            "final_state": self.final_state,
            "terminal": self.terminal,
            "ok": self.ok,
            "steps": [step.as_dict() for step in self.steps],
            "rejection": None if self.rejection is None else self.rejection.as_dict(),
            "path": self.path,
            "coverage": self.coverage.as_dict(),
        }


def run(machine: Machine, events: list[str] | tuple[str, ...], start: str | None = None) -> Run:
    """Apply events in order; stop at the first event the current state does not accept."""
    current = start or machine.initial
    if machine.state(current) is None:
        raise ValueError(f"unknown start state '{current}'")

    result = Run(machine=machine, start=current, events=tuple(events))
    for index, event in enumerate(events, start=1):
        transition = next((item for item in machine.outgoing(current) if item.event == event), None)
        if transition is None:
            result.rejection = Rejection(
                index=index,
                event=event,
                state=current,
                available=tuple(machine.events_from(current)),
            )
            return result
        result.steps.append(Step(index=index, event=event, source=current, target=transition.target))
        current = transition.target
    return result


@dataclass(frozen=True)
class Route:
    events: tuple[str, ...]
    states: tuple[str, ...]

    @property
    def length(self) -> int:
        return len(self.events)

    def as_dict(self) -> dict:
        return {"events": list(self.events), "states": list(self.states), "length": self.length}


def shortest_path(machine: Machine, target: str, start: str | None = None) -> Route | None:
    """Breadth-first search: the fewest events that take you from start to target."""
    origin = start or machine.initial
    if machine.state(origin) is None:
        raise ValueError(f"unknown start state '{origin}'")
    if machine.state(target) is None:
        raise ValueError(f"unknown target state '{target}'")
    if origin == target:
        return Route(events=(), states=(origin,))

    queue: deque[tuple[str, tuple[str, ...], tuple[str, ...]]] = deque([(origin, (), (origin,))])
    visited = {origin}
    while queue:
        current, events, path = queue.popleft()
        for transition in machine.outgoing(current):
            if transition.target in visited:
                continue
            next_events = (*events, transition.event)
            next_path = (*path, transition.target)
            if transition.target == target:
                return Route(events=next_events, states=next_path)
            visited.add(transition.target)
            queue.append((transition.target, next_events, next_path))
    return None


def reachable_states(machine: Machine, start: str | None = None) -> list[str]:
    """Every state reachable from start, in breadth-first order."""
    origin = start or machine.initial
    seen = [origin]
    queue = deque([origin])
    while queue:
        current = queue.popleft()
        for transition in machine.outgoing(current):
            if transition.target not in seen:
                seen.append(transition.target)
                queue.append(transition.target)
    return seen


def unexplored_events(machine: Machine, run_result: Run) -> dict[str, list[str]]:
    """Events that the run never tried, grouped by the state they belong to."""
    taken = {(step.source, step.event) for step in run_result.steps}
    missing: dict[str, list[str]] = {}
    for transition in machine.transitions:
        if (transition.source, transition.event) in taken:
            continue
        missing.setdefault(transition.source, []).append(transition.event)
    return missing
