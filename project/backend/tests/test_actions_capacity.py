"""Política de PICKUP/DROP: peso real y preferencia por objetos muertos.

Usa un escenario sintético con un objeto de peso 2 porque en scenario.json
todos pesan 1, y ahí un modelo que contara ítems en vez de peso pasaría igual.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))

from actions import successors  # noqa: E402
from problem import Problem  # noqa: E402
from state import State, free_capacity  # noqa: E402


def pickup_items(problem: Problem, state: State) -> set[str]:
    return {a.item for a, _, _ in successors(problem, state) if a.kind.startswith("pickup")}


def drop_items(problem: Problem, state: State) -> set[str]:
    return {a.item for a, _, _ in successors(problem, state) if a.kind.startswith("drop")}


def make_scenario(cargo_capacity: int = 3) -> dict[str, Any]:
    return {
        "robot": {
            "start": "A",
            "battery_max": 100,
            "battery_start": 100,
            "cargo_capacity": cargo_capacity,
        },
        "zones": [
            {"id": "A", "name": "A", "recharge": False},
            {"id": "B", "name": "B", "recharge": False},
        ],
        "corridors": [
            {"from": "A", "to": "B", "cost": 1, "door": None},
            {"from": "B", "to": "A", "cost": 1, "door": None},
        ],
        "doors": [
            {"id": "D1", "color": "x", "key": "KEY1", "state": "CLOSED", "between": ["A", "B"]},
        ],
        "keys": [{"id": "KEY1", "color": "x", "zone": "A", "weight": 1}],
        "tools": [{"id": "HEAVY_TOOL", "repairs": "X", "zone": "A", "weight": 2}],
        "materials": [{"type": "MAT", "zone": "A", "count": 1, "weight": 1}],
        "panels": [
            {
                "id": "PANEL1",
                "zone": "B",
                "damage": "X",
                "requires": {"tool": "HEAVY_TOOL", "material": "MAT"},
                "state": "DAMAGED",
            }
        ],
        "stations": [
            {"id": "ST1", "kind": "generator", "zone": "B", "state": "OFFLINE", "requires": {}}
        ],
        "chargers": [],
        "goal": {"stations_online": ["ST1"]},
        "action_costs": {"pickup": 1, "drop": 1, "interact": 2, "recharge": 3},
    }


def carrying(problem: Problem, **overrides: Any) -> State:
    return problem.initial_state()._replace(**overrides)


def test_pickup_blocked_by_real_weight() -> None:
    # Capacidad 2 y HEAVY_TOOL (peso 2) encima -> no queda hueco para MAT.
    problem = Problem(make_scenario(cargo_capacity=2))
    state = carrying(
        problem,
        payload_unique=frozenset({"HEAVY_TOOL"}),
        ground_unique=frozenset({("KEY1", "A")}),
    )
    assert free_capacity(problem, state) == 0
    items = pickup_items(problem, state)
    assert "MAT" not in items, f"MAT no debería caber con free_capacity=0, sucesores: {items}"


def test_drop_triggers_for_live_item_when_blocked() -> None:
    # Sin hueco para MAT y sin nada muerto encima: se ofrece soltar lo vivo.
    problem = Problem(make_scenario(cargo_capacity=2))
    state = carrying(
        problem,
        payload_unique=frozenset({"HEAVY_TOOL"}),
        ground_unique=frozenset({("KEY1", "A")}),
    )
    items = drop_items(problem, state)
    assert items == {"HEAVY_TOOL"}, (
        f"se esperaba ofrecer soltar el único objeto vivo cargado, se obtuvo {items}"
    )


def test_drop_prefers_dead_over_live() -> None:
    # KEY1 está muerta (su puerta ya está abierta) y la carga está llena.
    problem = Problem(make_scenario(cargo_capacity=3))
    state = carrying(
        problem,
        payload_unique=frozenset({"KEY1", "HEAVY_TOOL"}),
        ground_unique=frozenset(),
        doors_open=frozenset({"D1"}),
    )
    items = drop_items(problem, state)
    assert items == {"KEY1"}, f"se esperaba soltar solo el objeto muerto (KEY1), se obtuvo {items}"


def test_drop_not_triggered_when_nothing_blocked() -> None:
    # MAT cabe en el hueco que queda, así que no hay por qué soltar nada.
    problem = Problem(make_scenario(cargo_capacity=3))
    state = carrying(
        problem,
        payload_unique=frozenset({"HEAVY_TOOL"}),
        ground_unique=frozenset({("KEY1", "A")}),
    )
    assert drop_items(problem, state) == set(), (
        "no debería ofrecerse DROP si ningún PICKUP está bloqueado por espacio"
    )


if __name__ == "__main__":
    test_pickup_blocked_by_real_weight()
    test_drop_triggers_for_live_item_when_blocked()
    test_drop_prefers_dead_over_live()
    test_drop_not_triggered_when_nothing_blocked()
    print("Política PICKUP/DROP: OK")
