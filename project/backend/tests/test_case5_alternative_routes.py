"""Caso 5 — Rutas alternativas (README.MD §6).

    "Debe existir al menos una situación en la que puedan alcanzarse las mismas
     condiciones del mundo mediante diferentes rutas. La solución debe manejar
     correctamente esas rutas y conservar la alternativa que corresponda a la
     estrategia de búsqueda seleccionada y a su función de costo."

Las dos rutas del fixture tienen el mismo número de acciones, así que la
elección depende solo del costo: es lo que separa este caso del Caso 3.
"""

from __future__ import annotations

import copy
from typing import Any, Dict, List

from fixtures import (
    alternative_routes_scenario,
    demo_agent_plan,
    solve_scenario,
    tied_routes_scenario,
    zones_visited,
)

from simulator import goal_satisfied, load_scenario, simulate  # noqa: E402

# Ruta cara: legal y llega a la meta, pero cuesta 10 en vez de 7.
ROUTE_A_PLAN: List[Dict[str, Any]] = [
    {"op": "MOVE", "from": "Z1", "to": "ZA", "cost": 4},
    {"op": "MOVE", "from": "ZA", "to": "ZG", "cost": 4},
    {"op": "INTERACT", "target": "ST", "action": "ACTIVATE", "cost": 2},
]
ROUTE_A_COST = 10
OPTIMAL_COST = 7

# Óptimo actual de scenarios/scenario.json. Si se edita el escenario, cambia.
DEMO_OPTIMAL_COST = 80


def test_agent_takes_the_cheaper_of_two_routes() -> None:
    steps, cost = solve_scenario(alternative_routes_scenario())

    assert cost == OPTIMAL_COST, f"se esperaba costo 7, se obtuvo {cost}"
    assert zones_visited(steps) == ["Z1", "ZB", "ZG"], (
        f"debería ir por ZB (5) y no por ZA (8), fue por {zones_visited(steps)}"
    )


def test_expensive_route_is_genuinely_viable() -> None:
    # Si la alternativa descartada fuera ilegal, el caso no probaría nada.
    scenario = alternative_routes_scenario()
    final = simulate(scenario, ROUTE_A_PLAN)

    assert goal_satisfied(scenario, final), final["stations"]
    assert final["energy_spent"] == ROUTE_A_COST
    assert ROUTE_A_COST > OPTIMAL_COST


def test_tie_between_routes_returns_an_optimal_plan() -> None:
    # Empate: cualquiera vale, pero tiene que devolver una limpia.
    scenario = tied_routes_scenario()
    steps, cost = solve_scenario(scenario)
    route = zones_visited(steps)

    assert cost == OPTIMAL_COST, f"se esperaba costo 7 por cualquiera de las dos, fue {cost}"
    assert route in (["Z1", "ZA", "ZG"], ["Z1", "ZB", "ZG"]), f"ruta inesperada: {route}"

    final = simulate(scenario, steps)
    assert goal_satisfied(scenario, final), final["stations"]


def test_plan_has_no_repeated_zones() -> None:
    # Las rutas convergen en ZG: si el plan no repite zonas, CLOSED funciona.
    for scenario in (alternative_routes_scenario(), tied_routes_scenario()):
        steps, _ = solve_scenario(scenario)
        route = zones_visited(steps)
        assert len(route) == len(set(route)), f"el plan revisita zonas: {route}"


def test_demo_optimum_is_stable() -> None:
    # El demo también tiene rutas alternativas (Z2->Z5 cuesta 12; rodeando, 14).
    scenario, steps = demo_agent_plan()
    cost = sum(int(s["cost"]) for s in steps)

    assert cost == DEMO_OPTIMAL_COST, (
        f"el óptimo del escenario demo cambió: {cost} (esperado {DEMO_OPTIMAL_COST}). "
        "Si se editó scenario.json esto es esperable; si no, revisar el agente."
    )
    final = simulate(scenario, steps)
    assert goal_satisfied(scenario, final), final["stations"]


def test_agent_finds_the_back_route_when_the_main_door_is_impossible() -> None:
    # Sin KEY1, DOOR1 queda cerrada para siempre. El agente encuentra la ruta
    # trasera: Z1->Z4->Z3 a por KEY3, abre DOOR3 y entra a Z2 por Z5->Z2, que
    # no tiene puerta. Mismo resultado, ruta distinta y más cara.
    scenario = copy.deepcopy(load_scenario())
    scenario["keys"] = [k for k in scenario["keys"] if k["id"] != "KEY1"]

    steps, cost = solve_scenario(scenario)
    route = zones_visited(steps)
    opened = {s.get("target") for s in steps if s.get("action") == "OPEN_DOOR"}

    assert "DOOR1" not in opened, "sin KEY1 no puede abrir DOOR1"
    assert route[:2] == ["Z1", "Z4"], f"debería salir por el corredor sin puerta, fue {route[:2]}"
    assert "Z2" in route, "tiene que alcanzar Z2 (los materiales) por la ruta trasera"

    final = simulate(scenario, steps)
    assert goal_satisfied(scenario, final), final["stations"]
    assert cost > DEMO_OPTIMAL_COST, (
        "la ruta trasera debe costar más que el óptimo con KEY1 disponible"
    )


TESTS = [
    test_agent_takes_the_cheaper_of_two_routes,
    test_expensive_route_is_genuinely_viable,
    test_tie_between_routes_returns_an_optimal_plan,
    test_plan_has_no_repeated_zones,
    test_demo_optimum_is_stable,
    test_agent_finds_the_back_route_when_the_main_door_is_impossible,
]

if __name__ == "__main__":
    for t in TESTS:
        t()
    print(f"Caso 5 — Rutas alternativas: {len(TESTS)}/{len(TESTS)} OK")
