from __future__ import annotations

from pathlib import Path

from workflow_state_machine.machine import parse_machine
from workflow_state_machine.report import MachineReport
from workflow_state_machine.runner import run

EXAMPLES = Path(__file__).resolve().parent.parent / "examples"
ORDER = parse_machine((EXAMPLES / "order-fulfilment.json").read_text(encoding="utf-8"))
LEAKY = parse_machine((EXAMPLES / "leaky-process.json").read_text(encoding="utf-8"))


def test_text_report_lists_states_and_events() -> None:
    text = MachineReport(machine=ORDER, source="order.json").render()
    assert "Order fulfilment" in text
    assert "7 state(s), 9 transition(s)" in text
    assert "events: pack, hold, refund" in text
    assert "Validation: no problems found" in text


def test_text_report_shows_problems() -> None:
    text = MachineReport(machine=LEAKY).render()
    assert "2 error, 2 warning, 2 note" in text
    assert "dead-end" in text
    assert "orphan" in text


def test_run_section_success() -> None:
    report = MachineReport(machine=ORDER, run=run(ORDER, ["pay", "pack"]))
    section = report.render_run()
    assert "Run from 'created' with 2 event(s)" in section
    assert "1. pay          created -> paid" in section
    assert "final state 'packed'" in section
    assert "coverage 22%" in section


def test_run_section_rejection() -> None:
    report = MachineReport(machine=ORDER, run=run(ORDER, ["ship"]))
    section = report.render_run()
    assert "rejected at step 1" in section
    assert "available: pay, cancel" in section


def test_text_report_includes_run() -> None:
    text = MachineReport(machine=ORDER, run=run(ORDER, ["pay"])).render()
    assert "Run from 'created'" in text


def test_mermaid_graph() -> None:
    mermaid = MachineReport(machine=ORDER).render_mermaid()
    lines = mermaid.splitlines()
    assert lines[0] == "stateDiagram-v2"
    assert "  [*] --> created" in lines
    assert "  created --> paid: pay" in lines
    assert "  delivered --> [*]" in lines
    assert "  cancelled --> [*]" in lines


def test_markdown_report() -> None:
    markdown = MachineReport(machine=ORDER).render_markdown()
    assert markdown.startswith("# Order fulfilment")
    assert "```mermaid" in markdown
    assert "| `paid` | no | `pack`, `hold`, `refund` |" in markdown
    assert "No problems found." in markdown


def test_markdown_reports_problems() -> None:
    markdown = MachineReport(machine=LEAKY).render_markdown()
    assert "| error | `dead-end` |" in markdown


def test_json_shape() -> None:
    payload = MachineReport(machine=ORDER, source="order.json").as_dict()
    assert payload["ok"] is True
    assert payload["states"] == 7
    assert payload["transitions"] == 9
    assert payload["terminals"] == ["delivered", "cancelled"]
    assert payload["can_finish"] is True
    assert payload["problems"] == []
    assert "run" not in payload


def test_json_includes_run_and_unexplored() -> None:
    payload = MachineReport(machine=ORDER, run=run(ORDER, ["pay"])).as_dict()
    assert payload["run"]["final_state"] == "paid"
    assert payload["unexplored"]["created"] == ["cancel"]


def test_json_for_broken_machine() -> None:
    payload = MachineReport(machine=LEAKY).as_dict()
    assert payload["ok"] is False
    assert payload["errors"] == 2
    assert payload["dead_ends"] == ["archived", "orphan"]
