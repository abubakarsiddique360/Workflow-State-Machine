"""Text, markdown and Mermaid rendering for a machine."""

from __future__ import annotations

from dataclasses import dataclass, field

from workflow_state_machine import analysis
from workflow_state_machine.machine import Machine
from workflow_state_machine.runner import Run, unexplored_events


@dataclass
class MachineReport:
    machine: Machine
    source: str = "machine"
    run: Run | None = None
    problems: list[analysis.Problem] = field(init=False, default_factory=list)

    def __post_init__(self) -> None:
        self.problems = analysis.validate(self.machine)

    @property
    def errors(self) -> int:
        return analysis.error_count(self.problems)

    @property
    def ok(self) -> bool:
        return self.errors == 0

    def count(self, severity: str) -> int:
        return sum(1 for problem in self.problems if problem.severity == severity)

    def as_dict(self) -> dict:
        payload = {
            "source": self.source,
            "name": self.machine.name,
            "initial": self.machine.initial,
            "states": len(self.machine.states),
            "transitions": len(self.machine.transitions),
            "terminals": self.machine.terminals,
            "reachable": sorted(analysis.reachable(self.machine)),
            "unreachable": analysis.unreachable(self.machine),
            "dead_ends": analysis.dead_ends(self.machine),
            "can_finish": analysis.can_finish(self.machine),
            "ok": self.ok,
            "errors": self.errors,
            "warnings": self.count("warning"),
            "notes": self.count("note"),
            "problems": [problem.as_dict() for problem in self.problems],
        }
        if self.run is not None:
            payload["run"] = self.run.as_dict()
            payload["unexplored"] = unexplored_events(self.machine, self.run)
        return payload

    def render(self) -> str:
        machine = self.machine
        lines = [
            f"{machine.name}  -  {len(machine.states)} state(s), {len(machine.transitions)} transition(s)",
            f"initial '{machine.initial}'   terminal: {', '.join(machine.terminals) or 'none'}",
        ]

        lines += ["", "States"]
        for state in machine.states:
            marker = "terminal" if state.terminal else ""
            events = ", ".join(machine.events_from(state.name)) or "-"
            lines.append(f"  {state.name:<14}{marker:<10}events: {events}")

        if self.problems:
            lines += [
                "",
                f"Validation ({self.count('error')} error, {self.count('warning')} warning, {self.count('note')} note)",
            ]
            for problem in self.problems:
                lines.append(f"  {problem.severity:<8}{problem.code:<22}{problem.message}")
        else:
            lines += ["", "Validation: no problems found"]

        if self.run is not None:
            lines += ["", self.render_run()]

        return "\n".join(lines)

    def render_run(self) -> str:
        run = self.run
        assert run is not None
        lines = [f"Run from '{run.start}' with {len(run.events)} event(s)"]
        for step in run.steps:
            lines.append(f"  {step.index:>2}. {step.event:<12} {step.source} -> {step.target}")
        if run.rejection is not None:
            rejection = run.rejection
            available = ", ".join(rejection.available) or "none"
            lines.append(
                f"  rejected at step {rejection.index}: event '{rejection.event}' is not accepted "
                f"in '{rejection.state}' (available: {available})"
            )
        else:
            lines.append(f"  final state '{run.final_state}'" + (" (terminal)" if run.terminal else ""))
            lines.append(f"  transition coverage {run.coverage.percent:.0f}%")
        return "\n".join(lines)

    def render_markdown(self) -> str:
        machine = self.machine
        lines = [f"# {machine.name}", ""]
        lines.append(
            f"**{len(machine.states)} states - {len(machine.transitions)} transitions - initial `{machine.initial}`**"
        )
        lines += ["", "```mermaid", "stateDiagram-v2", self.mermaid_body(), "```"]

        lines += ["", "## States", "", "| State | Terminal | Events |", "| --- | --- | --- |"]
        for state in machine.states:
            events = ", ".join(f"`{event}`" for event in machine.events_from(state.name)) or "-"
            lines.append(f"| `{state.name}` | {'yes' if state.terminal else 'no'} | {events} |")

        lines += ["", "## Validation", ""]
        if not self.problems:
            lines.append("No problems found.")
        else:
            lines += ["| Severity | Code | Message |", "| --- | --- | --- |"]
            lines += [f"| {problem.severity} | `{problem.code}` | {problem.message} |" for problem in self.problems]

        if self.run is not None:
            lines += ["", "## Run", ""]
            for step in self.run.steps:
                lines.append(f"1. `{step.event}`: {step.source} -> {step.target}")
            if self.run.rejection is not None:
                lines.append(f"\nRejected: `{self.run.rejection.event}` in `{self.run.rejection.state}`.")
        return "\n".join(lines)

    def mermaid_body(self) -> str:
        machine = self.machine
        lines = [f"  [*] --> {machine.initial}"]
        for transition in machine.transitions:
            lines.append(f"  {transition.source} --> {transition.target}: {transition.event}")
        for state in machine.states:
            if state.terminal:
                lines.append(f"  {state.name} --> [*]")
        return "\n".join(lines)

    def render_mermaid(self) -> str:
        return "\n".join(["stateDiagram-v2", self.mermaid_body()])
