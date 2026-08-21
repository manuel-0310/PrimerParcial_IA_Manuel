"""Caso 4 — Sin solución (README.MD §6).

    "El agente debe terminar correctamente y devolver FAILURE cuando la misión
     no pueda completarse. No se aceptará una ejecución que quede atrapada
     indefinidamente explorando el espacio de estados."

Cubre fallo por topología y por recurso, la terminación, y cómo lo traduce el
endpoint.
"""

from __future__ import annotations

import copy
from typing import Any, Dict

from fixtures import battery_starved_scenario, unreachable_station_scenario

import main  # noqa: E402
from problem import Problem  # noqa: E402
from search import SearchLimitExceeded, solve  # noqa: E402
from simulator import load_scenario  # noqa: E402


def demo_variant(**mutations: Any) -> Dict[str, Any]:
    scenario = copy.deepcopy(load_scenario())
    scenario.update(mutations)
    return scenario


def test_failure_when_keys_cannot_reach_the_materials() -> None:
    # Quitar solo KEY1 no basta: queda la ruta trasera por DOOR3 y Z5->Z2 (ver
    # Caso 5). Sin KEY1 ni KEY3 el robot se queda en {Z1, Z3, Z4}, sin llegar
    # nunca a los materiales de Z2.
    scenario = demo_variant(
        keys=[k for k in load_scenario()["keys"] if k["id"] not in ("KEY1", "KEY3")]
    )
    assert solve(Problem.from_scenario(scenario)) is None


def test_failure_without_required_material() -> None:
    # Sin FUSE no hay PANEL_A, y sin él ninguna estación arranca.
    # Tarda ~30 s: recorre todo el espacio alcanzable del escenario real.
    scenario = demo_variant(
        materials=[m for m in load_scenario()["materials"] if m["type"] != "FUSE"]
    )
    assert solve(Problem.from_scenario(scenario)) is None


def test_failure_with_unreachable_station() -> None:
    # Una estación de la meta en una zona sin corredores.
    assert solve(Problem.from_scenario(unreachable_station_scenario())) is None


def test_failure_when_battery_insufficient() -> None:
    # La meta se alcanza en el grafo, pero no hay energía ni dónde recargar.
    assert solve(Problem.from_scenario(battery_starved_scenario())) is None


def test_failure_searches_terminate_by_exhausting_open() -> None:
    # OPEN se vacía muy por debajo del tope: el FAILURE está demostrado.
    for scenario in (unreachable_station_scenario(), battery_starved_scenario()):
        assert solve(Problem.from_scenario(scenario), expansion_limit=10_000) is None


def test_search_limit_guard_is_real() -> None:
    # Con un presupuesto absurdo aborta en vez de girar indefinidamente.
    problem = Problem.from_scenario(load_scenario())
    try:
        solve(problem, expansion_limit=10)
    except SearchLimitExceeded:
        return
    raise AssertionError("se esperaba SearchLimitExceeded con expansion_limit=10")


def test_api_returns_failure_envelope() -> None:
    # El endpoint devuelve el sobre de FAILURE, no un error 500.
    response = main.solve(unreachable_station_scenario())

    assert response["solution_found"] is False
    assert response["total_cost"] == 0
    assert response["steps"] == []
    assert response["message"]


def test_api_reports_failure_when_search_limit_is_hit() -> None:
    # Se inyecta la excepción en vez de provocarla con una instancia enorme,
    # para que el test sea instantáneo.
    original = main.run_search

    def boom(_problem: Any) -> Any:
        raise SearchLimitExceeded("límite simulado")

    main.run_search = boom
    try:
        response = main.solve(unreachable_station_scenario())
    finally:
        main.run_search = original

    assert response["solution_found"] is False
    assert response["steps"] == []
    assert "límite simulado" in response["message"]


TESTS = [
    test_failure_when_keys_cannot_reach_the_materials,
    test_failure_without_required_material,
    test_failure_with_unreachable_station,
    test_failure_when_battery_insufficient,
    test_failure_searches_terminate_by_exhausting_open,
    test_search_limit_guard_is_real,
    test_api_returns_failure_envelope,
    test_api_reports_failure_when_search_limit_is_hit,
]

if __name__ == "__main__":
    for t in TESTS:
        t()
    print(f"Caso 4 — Sin solución (FAILURE): {len(TESTS)}/{len(TESTS)} OK")
