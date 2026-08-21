"""Caso 1 — Estados equivalentes (README.MD §6).

    "Dos configuraciones físicamente equivalentes deben producir el mismo
     estado lógico, aunque hayan sido generadas mediante historias diferentes."

Verifica `design.md § Cuándo dos configuraciones son el mismo estado` y
`§ Relevancia: objetos que ya no cambian el futuro`.
"""

from __future__ import annotations

from fixtures import demo_problem  # noqa: F401  (bootstrapea sys.path)

import state as st  # noqa: E402
from actions import successors  # noqa: E402
from problem import Problem  # noqa: E402
from search import _dominance_key  # noqa: E402
from state import State  # noqa: E402


def apply_pickup(problem: Problem, state: State, item: str) -> State:
    """Recoge `item` pasando por successors(), no por apply_* directamente.

    Lo que hay que demostrar es que convergen las historias que el agente
    genera de verdad.
    """
    for action, next_state, _ in successors(problem, state):
        if action.kind.startswith("pickup") and action.item == item:
            return next_state
    raise AssertionError(f"PICKUP {item} no fue generado en la zona {state.zone}")


def in_zone(problem: Problem, zone: str) -> State:
    return problem.initial_state()._replace(zone=zone)


def test_pickup_order_produces_same_state() -> None:
    # Z2 tiene CHIP y CABLE en el suelo. Recogerlos en un orden o en el otro son
    # dos historias distintas que llegan al mismo mundo físico.
    problem = demo_problem()
    base = in_zone(problem, "Z2")

    chip_first = apply_pickup(problem, apply_pickup(problem, base, "CHIP"), "CABLE")
    cable_first = apply_pickup(problem, apply_pickup(problem, base, "CABLE"), "CHIP")

    assert chip_first == cable_first, (
        "el orden de recogida no debería cambiar el estado:\n"
        f"  CHIP->CABLE: {chip_first}\n  CABLE->CHIP: {cable_first}"
    )
    # El hash importa aparte: CLOSED es un dict.
    assert hash(chip_first) == hash(cable_first)


def test_equivalent_states_collapse_in_closed() -> None:
    # Misma clave de CLOSED: la segunda historia se poda al llegar.
    problem = demo_problem()
    base = in_zone(problem, "Z2")

    chip_first = apply_pickup(problem, apply_pickup(problem, base, "CHIP"), "CABLE")
    cable_first = apply_pickup(problem, apply_pickup(problem, base, "CABLE"), "CHIP")

    assert _dominance_key(chip_first) == _dominance_key(cable_first)


def test_dead_key_position_is_forgotten() -> None:
    # KEY1 solo abre DOOR1: con la puerta abierta, dónde quedó ya no importa.
    problem = demo_problem()
    base = problem.initial_state()._replace(doors_open=frozenset({"DOOR1"}))
    others = frozenset((i, z) for (i, z) in base.ground_unique if i != "KEY1")

    dropped_in_z1 = base._replace(ground_unique=others | {("KEY1", "Z1")})
    dropped_in_z4 = base._replace(ground_unique=others | {("KEY1", "Z4")})

    # Distintos como tuplas, pero el mismo mundo una vez canonicalizados.
    assert dropped_in_z1 != dropped_in_z4
    assert st.canonicalize(problem, dropped_in_z1) == st.canonicalize(
        problem, dropped_in_z4
    ), "dos posiciones de un objeto muerto deberían colapsar al mismo estado"


def test_material_units_have_no_identity() -> None:
    # Z2 tiene FUSE x2: coger uno, o coger dos y devolver uno, da lo mismo.
    # Aquí sí se llama a apply_* directamente porque successors() no genera el
    # segundo PICKUP (solo un panel pendiente lo consume).
    problem = demo_problem()
    base = in_zone(problem, "Z2")
    cost = problem.action_costs["pickup"]

    took_one = st.apply_pickup_material(problem, base, "FUSE", cost)

    took_two = st.apply_pickup_material(problem, took_one, "FUSE", cost)
    returned_one = st.apply_drop_material(
        problem, took_two, "FUSE", problem.action_costs["drop"]
    )

    # Mismo mundo; la única diferencia es la batería del rodeo (ver Caso 2).
    assert _dominance_key(took_one) == _dominance_key(returned_one)
    assert took_one._replace(battery=0) == returned_one._replace(battery=0)
    assert took_one.battery > returned_one.battery


TESTS = [
    test_pickup_order_produces_same_state,
    test_equivalent_states_collapse_in_closed,
    test_dead_key_position_is_forgotten,
    test_material_units_have_no_identity,
]

if __name__ == "__main__":
    for t in TESTS:
        t()
    print(f"Caso 1 — Estados equivalentes: {len(TESTS)}/{len(TESTS)} OK")
