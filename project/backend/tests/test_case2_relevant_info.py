"""Caso 2 — Información relevante (README.MD §6).

    "Dos configuraciones que difieran en información que puede cambiar las
     acciones futuras deben mantenerse como estados diferentes."

Cada test comprueba las dos mitades: que los estados son distintos, y que esa
diferencia cambia `Applicable(s)` — que es lo que justifica guardarla.
"""

from __future__ import annotations

from typing import Set, Tuple

from fixtures import demo_problem  # noqa: F401  (bootstrapea sys.path)

from actions import successors  # noqa: E402
from problem import Problem  # noqa: E402
from search import _is_dominated  # noqa: E402
from state import State  # noqa: E402


def moves(problem: Problem, state: State) -> Set[Tuple[str, str]]:
    return {
        (a.zone_from, a.zone_to) for a, _, _ in successors(problem, state) if a.kind == "move"
    }


def pickups(problem: Problem, state: State) -> Set[str]:
    return {a.item for a, _, _ in successors(problem, state) if a.kind.startswith("pickup")}


def repairs(problem: Problem, state: State) -> Set[str]:
    return {a.target for a, _, _ in successors(problem, state) if a.kind == "repair"}


def materials(problem: Problem, **counts: int) -> Tuple[int, ...]:
    vec = [0] * len(problem.material_types)
    for material_type, count in counts.items():
        vec[problem.material_index[material_type]] = count
    return tuple(vec)


def test_battery_changes_applicable_actions() -> None:
    # Desde Z1 los corredores cuestan 4 y 8: con 3 de batería no se puede mover
    # a ninguna parte, con 10 sí.
    problem = demo_problem()
    base = problem.initial_state()._replace(zone="Z1", doors_open=frozenset({"DOOR1"}))

    starved = base._replace(battery=3)
    charged = base._replace(battery=10)

    assert starved != charged
    assert moves(problem, starved) == set(), (
        f"con batería 3 ningún corredor es pagable, se generó {moves(problem, starved)}"
    )
    assert moves(problem, charged) == {("Z1", "Z2"), ("Z1", "Z4")}


def test_dominance_keeps_higher_battery_at_higher_cost() -> None:
    # Solo se descarta si ya se vio algo con g menor o igual Y más batería.
    seen = [(10, 50)]  # (g, batería) ya registrado para esta clave

    assert _is_dominated(seen, 12, 60) is False, (
        "más batería a mayor costo no está dominado: hay que conservarlo"
    )
    assert _is_dominated(seen, 12, 40) is True, "peor en ambas dimensiones: dominado"
    assert _is_dominated(seen, 10, 50) is True, "idéntico: dominado"
    assert _is_dominated(seen, 8, 60) is False, "mejor en ambas: no dominado por el viejo"


def test_open_door_is_relevant() -> None:
    # Una puerta abierta habilita un MOVE que antes no existía.
    problem = demo_problem()
    base = problem.initial_state()._replace(zone="Z1", battery=50)

    closed = base._replace(doors_open=frozenset())
    opened = base._replace(doors_open=frozenset({"DOOR1"}))

    assert closed != opened
    assert ("Z1", "Z2") not in moves(problem, closed)
    assert ("Z1", "Z2") in moves(problem, opened)


def test_live_tool_position_is_kept() -> None:
    # Al revés que la llave muerta del Caso 1: si sigue viva, su zona importa.
    problem = demo_problem()
    base = problem.initial_state()._replace(zone="Z4", battery=50)
    others = frozenset((i, z) for (i, z) in base.ground_unique if i != "MULTITOOL")

    in_z3 = base._replace(ground_unique=others | {("MULTITOOL", "Z3")})
    in_z4 = base._replace(ground_unique=others | {("MULTITOOL", "Z4")})

    assert in_z3 != in_z4
    assert "MULTITOOL" not in pickups(problem, in_z3), "no está en la zona del robot"
    assert "MULTITOOL" in pickups(problem, in_z4)


def test_payload_changes_repair_applicability() -> None:
    # PANEL_A exige MULTITOOL: con la herramienta equivocada no hay REPAIR.
    problem = demo_problem()
    base = problem.initial_state()._replace(
        zone="Z4", battery=50, payload_materials=materials(problem, FUSE=1)
    )

    right_tool = base._replace(payload_unique=frozenset({"MULTITOOL"}))
    wrong_tool = base._replace(payload_unique=frozenset({"SOLDERING"}))

    assert right_tool != wrong_tool
    assert "PANEL_A" in repairs(problem, right_tool)
    assert "PANEL_A" not in repairs(problem, wrong_tool)


TESTS = [
    test_battery_changes_applicable_actions,
    test_dominance_keeps_higher_battery_at_higher_cost,
    test_open_door_is_relevant,
    test_live_tool_position_is_kept,
    test_payload_changes_repair_applicability,
]

if __name__ == "__main__":
    for t in TESTS:
        t()
    print(f"Caso 2 — Información relevante: {len(TESTS)}/{len(TESTS)} OK")
