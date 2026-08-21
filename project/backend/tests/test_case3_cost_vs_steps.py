"""Caso 3 — Costos diferentes (README.MD §6).

    "Debe existir al menos una instancia donde la solución con menor cantidad
     de acciones no sea la solución de menor costo. La estrategia seleccionada
     debe comportarse de acuerdo con la propiedad que el estudiante afirmó en
     design.md."

Instancia donde el plan más corto no es el más barato. Se contrasta con un BFS
sobre el mismo generador de sucesores para ver que la diferencia viene de la
estrategia y no de cómo está formulado el problema.
"""

from __future__ import annotations

from collections import deque
from typing import Any, Dict, List, Optional, Tuple

from fixtures import cost_vs_steps_scenario, solve_scenario, zones_visited

from actions import successors  # noqa: E402
from problem import Problem  # noqa: E402
from simulator import goal_satisfied, simulate  # noqa: E402

# Plan de menos acciones: legal y llega a la meta, pero cuesta casi el triple.
SHORT_PLAN: List[Dict[str, Any]] = [
    {"op": "MOVE", "from": "Z1", "to": "ZG", "cost": 20},
    {"op": "INTERACT", "target": "ST", "action": "ACTIVATE", "cost": 2},
]
SHORT_PLAN_COST = 22

AGENT_PLAN_STEPS = 3
AGENT_PLAN_COST = 8


def bfs_plan(scenario: Dict[str, Any]) -> Tuple[Optional[List[Any]], int]:
    """BFS sobre el mismo successors() del agente: cola FIFO y meta al generar."""
    problem = Problem.from_scenario(scenario)
    start = problem.initial_state()
    if problem.is_goal(start):
        return [], 0

    frontier = deque([(start, [], 0)])
    seen = {start}
    while frontier:
        state, path, g = frontier.popleft()
        for action, next_state, cost in successors(problem, state):
            if next_state in seen:
                continue
            extended = path + [action]
            if problem.is_goal(next_state):
                return extended, g + cost
            seen.add(next_state)
            frontier.append((next_state, extended, g + cost))
    return None, 0


def test_agent_returns_cheaper_plan_with_more_actions() -> None:
    steps, cost = solve_scenario(cost_vs_steps_scenario())

    assert len(steps) == AGENT_PLAN_STEPS, f"se esperaban 3 pasos, se obtuvo {steps}"
    assert cost == AGENT_PLAN_COST, f"se esperaba costo 8, se obtuvo {cost}"
    assert zones_visited(steps) == ["Z1", "ZM", "ZG"]

    directo = [s for s in steps if s["op"] == "MOVE" and s["from"] == "Z1" and s["to"] == "ZG"]
    assert not directo, "el agente tomó el corredor directo, que es el caro"


def test_shorter_plan_exists_and_is_legal_but_costlier() -> None:
    # El plan corto no es ilegal ni imposible: el simulador lo acepta entero.
    scenario = cost_vs_steps_scenario()
    final = simulate(scenario, SHORT_PLAN)

    assert goal_satisfied(scenario, final), final["stations"]
    assert final["energy_spent"] == SHORT_PLAN_COST

    agent_steps, agent_cost = solve_scenario(scenario)
    assert len(SHORT_PLAN) < len(agent_steps), "el plan alternativo debe tener menos acciones"
    assert SHORT_PLAN_COST > agent_cost, "...y aun así costar más"


def test_bfs_would_choose_the_shorter_costlier_plan() -> None:
    scenario = cost_vs_steps_scenario()
    bfs_actions, bfs_cost = bfs_plan(scenario)
    _, ucs_cost = solve_scenario(scenario)

    assert bfs_actions is not None
    assert len(bfs_actions) == len(SHORT_PLAN), "BFS minimiza acciones, no costo"
    assert bfs_cost == SHORT_PLAN_COST
    assert bfs_cost > ucs_cost, (
        f"BFS devolvió costo {bfs_cost} y UCS {ucs_cost}: la elección de "
        "estrategia es exactamente lo que separa ambos planes"
    )


def test_agent_plan_is_legal_in_simulator() -> None:
    scenario = cost_vs_steps_scenario()
    steps, cost = solve_scenario(scenario)
    final = simulate(scenario, steps)

    assert goal_satisfied(scenario, final), final["stations"]
    assert final["energy_spent"] == cost


TESTS = [
    test_agent_returns_cheaper_plan_with_more_actions,
    test_shorter_plan_exists_and_is_legal_but_costlier,
    test_bfs_would_choose_the_shorter_costlier_plan,
    test_agent_plan_is_legal_in_simulator,
]

if __name__ == "__main__":
    for t in TESTS:
        t()
    print(f"Caso 3 — Costos ≠ número de acciones: {len(TESTS)}/{len(TESTS)} OK")
