"""Read a state machine definition from JSON."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any


class MachineError(ValueError):
    """Raised when a machine definition is structurally invalid."""


@dataclass(frozen=True)
class State:
    name: str
    terminal: bool = False
    description: str = ""

    def as_dict(self) -> dict:
        return {"name": self.name, "terminal": self.terminal, "description": self.description}


@dataclass(frozen=True)
class Transition:
    source: str
    event: str
    target: str
    note: str = ""

    def as_dict(self) -> dict:
        return {"from": self.source, "event": self.event, "to": self.target, "note": self.note}


@dataclass
class Machine:
    name: str
    initial: str
    states: list[State] = field(default_factory=list)
    transitions: list[Transition] = field(default_factory=list)

    @property
    def state_names(self) -> list[str]:
        return [state.name for state in self.states]

    def state(self, name: str) -> State | None:
        for state in self.states:
            if state.name == name:
                return state
        return None

    @property
    def terminals(self) -> list[str]:
        return [state.name for state in self.states if state.terminal]

    def outgoing(self, source: str) -> list[Transition]:
        return [transition for transition in self.transitions if transition.source == source]

    def events_from(self, source: str) -> list[str]:
        return [transition.event for transition in self.outgoing(source)]

    def is_terminal(self, name: str) -> bool:
        state = self.state(name)
        return bool(state and state.terminal)


def _required_text(raw: dict, key: str, where: str) -> str:
    value = raw.get(key)
    if not isinstance(value, str) or not value.strip():
        raise MachineError(f"{where}: '{key}' must be a non-empty string")
    return value.strip()


def _optional_text(raw: dict, key: str, where: str) -> str:
    value = raw.get(key)
    if value is None:
        return ""
    if not isinstance(value, str):
        raise MachineError(f"{where}: '{key}' must be a string")
    return value.strip()


def parse_machine(payload: str | dict) -> Machine:
    """Parse and structurally validate a machine definition.

    Structural problems are fatal: duplicate states, an initial state that does not
    exist, or a transition that points at a state which was never declared.
    """
    document: Any = payload
    if isinstance(payload, str):
        try:
            document = json.loads(payload)
        except json.JSONDecodeError as exc:
            raise MachineError(f"machine is not valid JSON: {exc.msg} at line {exc.lineno}") from exc

    if not isinstance(document, dict):
        raise MachineError("machine must be a JSON object")

    raw_states = document.get("states")
    if not isinstance(raw_states, list) or not raw_states:
        raise MachineError("machine needs a non-empty 'states' list")

    states: list[State] = []
    seen: set[str] = set()
    for position, raw in enumerate(raw_states, start=1):
        if not isinstance(raw, dict):
            raise MachineError(f"state #{position} must be an object")
        name = _required_text(raw, "name", f"state #{position}")
        if name in seen:
            raise MachineError(f"duplicate state '{name}'")
        seen.add(name)
        terminal = raw.get("terminal", False)
        if not isinstance(terminal, bool):
            raise MachineError(f"state '{name}': 'terminal' must be true or false")
        states.append(
            State(name=name, terminal=terminal, description=_optional_text(raw, "description", f"state '{name}'"))
        )

    initial = _required_text(document, "initial", "machine")
    if initial not in seen:
        raise MachineError(f"initial state '{initial}' is not declared in 'states'")

    raw_transitions = document.get("transitions", [])
    if not isinstance(raw_transitions, list):
        raise MachineError("'transitions' must be a list")

    transitions: list[Transition] = []
    pairs: set[tuple[str, str]] = set()
    for position, raw in enumerate(raw_transitions, start=1):
        if not isinstance(raw, dict):
            raise MachineError(f"transition #{position} must be an object")
        source = _required_text(raw, "from", f"transition #{position}")
        event = _required_text(raw, "event", f"transition #{position}")
        target = _required_text(raw, "to", f"transition #{position}")
        for role, name in (("from", source), ("to", target)):
            if name not in seen:
                raise MachineError(f"transition #{position}: '{role}' references unknown state '{name}'")
        if (source, event) in pairs:
            raise MachineError(f"state '{source}' has two transitions for event '{event}'")
        pairs.add((source, event))
        transitions.append(
            Transition(
                source=source, event=event, target=target, note=_optional_text(raw, "note", f"transition #{position}")
            )
        )

    raw_name = document.get("name")
    if raw_name is not None and not isinstance(raw_name, str):
        raise MachineError("'name' must be a string")
    name = (raw_name or "State machine").strip() or "State machine"

    return Machine(name=name, initial=initial, states=states, transitions=transitions)


def load_machine(path: str) -> Machine:
    from pathlib import Path

    try:
        text = Path(path).read_text(encoding="utf-8-sig")
    except OSError as exc:
        raise MachineError(f"cannot read {path}: {exc.strerror or exc}") from exc
    return parse_machine(text)
