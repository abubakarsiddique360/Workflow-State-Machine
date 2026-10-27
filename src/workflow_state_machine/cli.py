"""Command line entry point: validate, run, path, graph, states."""

from __future__ import annotations

import argparse
import json
import sys

from workflow_state_machine.machine import MachineError, load_machine
from workflow_state_machine.report import MachineReport
from workflow_state_machine.runner import reachable_states, run, shortest_path

EVENT_SEPARATORS = (",", ">")


def split_events(text: str) -> list[str]:
    """Accept 'pay,pack,ship' or 'pay > pack > ship'."""
    normalised = text
    for separator in EVENT_SEPARATORS[1:]:
        normalised = normalised.replace(separator, EVENT_SEPARATORS[0])
    return [part.strip() for part in normalised.split(EVENT_SEPARATORS[0]) if part.strip()]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="workflow-fsm",
        description="Validate, simulate and draw a finite state machine defined in JSON.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    validate = sub.add_parser("validate", help="check reachability, dead ends and terminals")
    validate.add_argument("file")
    validate.add_argument("--json", action="store_true")
    validate.add_argument("--markdown", action="store_true")

    run_cmd = sub.add_parser("run", help="apply a comma separated list of events")
    run_cmd.add_argument("file")
    run_cmd.add_argument("--events", required=True, help="events to apply, for example 'pay,pack,ship'")
    run_cmd.add_argument("--from", dest="start", help="start from this state instead of the initial one")
    run_cmd.add_argument("--json", action="store_true")

    path_cmd = sub.add_parser("path", help="fewest events that reach a target state")
    path_cmd.add_argument("file")
    path_cmd.add_argument("--to", required=True, help="target state")
    path_cmd.add_argument("--from", dest="start")
    path_cmd.add_argument("--json", action="store_true")

    graph = sub.add_parser("graph", help="Mermaid state diagram")
    graph.add_argument("file")

    states = sub.add_parser("states", help="one line per state")
    states.add_argument("file")

    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    try:
        machine = load_machine(args.file)
    except MachineError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    source = args.file.split("\\")[-1].split("/")[-1]

    if args.command == "states":
        for state in machine.states:
            events = ", ".join(machine.events_from(state.name)) or "-"
            flag = "terminal" if state.terminal else ""
            print(f"{state.name:<16}{flag:<10}{events}")
        return 0

    if args.command == "graph":
        print(MachineReport(machine=machine, source=source).render_mermaid())
        return 0

    if args.command == "path":
        try:
            route = shortest_path(machine, args.to, args.start)
        except ValueError as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 2
        if route is None:
            print(f"error: no route from '{args.start or machine.initial}' to '{args.to}'", file=sys.stderr)
            return 1
        if args.json:
            print(json.dumps(route.as_dict(), indent=2))
        else:
            print(f"{len(route.events)} event(s): {' > '.join(route.events) or '(already there)'}")
            print(f"{' > '.join(route.states)}")
        return 0

    if args.command == "run":
        try:
            result = run(machine, split_events(args.events), args.start)
        except ValueError as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 2
        report = MachineReport(machine=machine, source=source, run=result)
        if args.json:
            print(json.dumps(report.as_dict(), indent=2))
        else:
            print(f"{machine.name}")
            print(report.render_run())
        return 0 if result.ok else 1

    report = MachineReport(machine=machine, source=source)
    if args.json:
        print(json.dumps(report.as_dict(), indent=2))
    elif args.markdown:
        print(report.render_markdown())
    else:
        print(report.render())
    if not report.ok:
        return 1
    print()
    print("reachable from initial: " + ", ".join(reachable_states(machine)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
