from __future__ import annotations

import json
from pathlib import Path

from workflow_state_machine.cli import main, split_events

EXAMPLES = Path(__file__).resolve().parent.parent / "examples"
ORDER = EXAMPLES / "order-fulfilment.json"
LEAKY = EXAMPLES / "leaky-process.json"


def test_split_events() -> None:
    assert split_events("pay,pack,ship") == ["pay", "pack", "ship"]
    assert split_events("pay > pack > ship") == ["pay", "pack", "ship"]
    assert split_events(" pay ,, pack ") == ["pay", "pack"]
    assert split_events("") == []


def test_validate_sound(capsys) -> None:
    assert main(["validate", str(ORDER)]) == 0
    out = capsys.readouterr().out
    assert "no problems found" in out
    assert "reachable from initial" in out


def test_validate_broken(capsys) -> None:
    assert main(["validate", str(LEAKY)]) == 1
    assert "dead-end" in capsys.readouterr().out


def test_validate_json(capsys) -> None:
    assert main(["validate", str(LEAKY), "--json"]) == 1
    payload = json.loads(capsys.readouterr().out)
    assert payload["ok"] is False
    assert payload["errors"] == 2


def test_validate_markdown(capsys) -> None:
    assert main(["validate", str(ORDER), "--markdown"]) == 0
    assert "stateDiagram-v2" in capsys.readouterr().out


def test_run_success(capsys) -> None:
    assert main(["run", str(ORDER), "--events", "pay,pack,ship,deliver"]) == 0
    out = capsys.readouterr().out
    assert "final state 'delivered'" in out
    assert "coverage 44%" in out


def test_run_rejected(capsys) -> None:
    assert main(["run", str(ORDER), "--events", "ship"]) == 1
    assert "rejected at step 1" in capsys.readouterr().out


def test_run_json(capsys) -> None:
    assert main(["run", str(ORDER), "--events", "pay", "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["run"]["final_state"] == "paid"


def test_run_from_state(capsys) -> None:
    assert main(["run", str(ORDER), "--events", "release", "--from", "on_hold"]) == 0
    assert "final state 'paid'" in capsys.readouterr().out


def test_run_unknown_start(capsys) -> None:
    assert main(["run", str(ORDER), "--events", "pay", "--from", "nowhere"]) == 2
    assert "unknown start state" in capsys.readouterr().err


def test_path_command(capsys) -> None:
    assert main(["path", str(ORDER), "--to", "delivered"]) == 0
    out = capsys.readouterr().out
    assert "4 event(s): pay > pack > ship > deliver" in out
    assert "created > paid > packed > shipped > delivered" in out


def test_path_json(capsys) -> None:
    assert main(["path", str(ORDER), "--to", "cancelled", "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["events"] == ["cancel"]


def test_path_without_route(tmp_path, capsys) -> None:
    path = tmp_path / "island.json"
    path.write_text(
        json.dumps(
            {
                "initial": "a",
                "states": [{"name": "a"}, {"name": "b"}],
                "transitions": [{"from": "a", "event": "cancel", "to": "a"}],
            }
        ),
        encoding="utf-8",
    )
    assert main(["path", str(path), "--to", "b"]) == 1
    assert "no route" in capsys.readouterr().err


def test_graph_command(capsys) -> None:
    assert main(["graph", str(ORDER)]) == 0
    assert capsys.readouterr().out.startswith("stateDiagram-v2")


def test_states_command(capsys) -> None:
    assert main(["states", str(ORDER)]) == 0
    out = capsys.readouterr().out
    assert "delivered" in out
    assert "terminal" in out


def test_missing_file(tmp_path, capsys) -> None:
    assert main(["validate", str(tmp_path / "nope.json")]) == 2
    assert "cannot read" in capsys.readouterr().err


def test_invalid_definition(tmp_path, capsys) -> None:
    path = tmp_path / "bad.json"
    path.write_text('{"initial": "ghost", "states": [{"name": "a"}]}', encoding="utf-8")
    assert main(["validate", str(path)]) == 2
    assert "not declared" in capsys.readouterr().err
