"""Tests: el agente UCS resuelve el escenario demo con un plan legal y óptimo."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))

from fixtures import demo_agent_plan  # noqa: E402

from demo_plan import build_demo_plan  # noqa: E402
from simulator import goal_satisfied, load_scenario, simulate  # noqa: E402

VALID_OPS = {"MOVE", "PICKUP", "DROP", "INTERACT"}
VALID_INTERACT = {"OPEN_DOOR", "REPAIR", "ACTIVATE", "RECHARGE"}


def agent_plan() -> tuple[dict, list[dict]]:
    return demo_agent_plan()


def test_plan_is_legal_and_reaches_goal() -> None:
    scenario, steps = agent_plan()
    final = simulate(scenario, steps)
    assert goal_satisfied(scenario, final), final["stations"]
    assert final["energy_spent"] == sum(s["cost"] for s in steps)


def test_plan_respects_closed_contract() -> None:
    _, steps = agent_plan()
    for step in steps:
        assert step["op"] in VALID_OPS, f"op fuera del contrato: {step}"
        if step["op"] == "INTERACT":
            assert step["action"] in VALID_INTERACT, f"action fuera del contrato: {step}"
            if step["action"] == "REPAIR":
                assert "consumes" in step, f"REPAIR sin consumes explícito: {step}"


def test_costs_match_scenario() -> None:
    scenario, steps = agent_plan()
    costs = scenario["action_costs"]
    for step in steps:
        if step["op"] == "MOVE":
            corridor = next(
                c
                for c in scenario["corridors"]
                if c["from"] == step["from"] and c["to"] == step["to"]
            )
            assert step["cost"] == corridor["cost"], f"costo de corredor incorrecto: {step}"
        elif step["op"] == "PICKUP":
            assert step["cost"] == costs["pickup"]
        elif step["op"] == "DROP":
            assert step["cost"] == costs["drop"]
        elif step["action"] == "RECHARGE":
            assert step["cost"] == costs["recharge"]
        else:
            assert step["cost"] == costs["interact"]


def test_agent_beats_handcrafted_demo_plan() -> None:
    scenario, steps = agent_plan()
    agent_cost = sum(s["cost"] for s in steps)
    demo_cost = build_demo_plan(scenario)["total_cost"]
    assert agent_cost <= demo_cost, (
        f"UCS ({agent_cost}) debería costar <= el plan artesanal ({demo_cost})"
    )


if __name__ == "__main__":
    test_plan_is_legal_and_reaches_goal()
    test_plan_respects_closed_contract()
    test_costs_match_scenario()
    test_agent_beats_handcrafted_demo_plan()
    _, plan_steps = agent_plan()
    print(
        f"El agente resuelve la demo: {len(plan_steps)} pasos, "
        f"costo {sum(s['cost'] for s in plan_steps)} "
        f"(artesanal: {build_demo_plan(load_scenario())['total_cost']})."
    )
