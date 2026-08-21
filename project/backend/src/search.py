"""UCS / Graph Search con dominancia de batería — ver project/design.md § Estrategia de búsqueda."""

from __future__ import annotations

import time
from typing import Any, Optional

from actions import Action, successors
from state import State

# Topes de seguridad, no parte de la estrategia. Un tope demasiado bajo corta
# búsquedas que sí tienen solución: arrancar en Z3 necesita ~2,8 M expansiones.
DEFAULT_EXPANSION_LIMIT = 15_000_000
DEFAULT_TIME_LIMIT_S = 180.0

# Consultar el reloj en cada expansión se nota; cada 4096 no.
_TIME_CHECK_EVERY = 4096


class Node:
    __slots__ = ("state", "parent", "action", "g")

    def __init__(
        self,
        state: State,
        parent: Optional["Node"],
        action: Optional[Action],
        g: int,
    ) -> None:
        self.state = state
        self.parent = parent
        self.action = action
        self.g = g


class SearchLimitExceeded(RuntimeError):
    pass


def _dominance_key(state: State) -> tuple:
    """Clave de CLOSED: el estado sin la batería."""
    return (
        state.zone,
        state.payload_unique,
        state.payload_materials,
        state.ground_unique,
        state.ground_materials,
        state.doors_open,
        state.panels_repaired,
        state.stations_online,
    )


def _is_dominated(entries: list[tuple[int, int]], g: int, battery: int) -> bool:
    for g2, b2 in entries:
        if g2 <= g and b2 >= battery:
            return True
    return False


def solve(
    problem: Any,
    expansion_limit: int = DEFAULT_EXPANSION_LIMIT,
    time_limit_s: Optional[float] = DEFAULT_TIME_LIMIT_S,
) -> Optional[Node]:
    """UCS sobre Graph Search. Devuelve el nodo meta, o None si no existe plan.

    OPEN son buckets indexados por g en vez de un heap: como todos los costos
    son enteros positivos, vaciar los buckets en orden creciente ya expande por
    g no decreciente, en O(1) por operación.

    Agotar un tope lanza SearchLimitExceeded en vez de devolver None: "no dio
    tiempo" no es "no hay plan". time_limit_s=None desactiva el tope de tiempo.
    """
    started = time.monotonic()
    root = Node(problem.initial_state(), None, None, 0)

    buckets: dict[int, list[Node]] = {0: [root]}
    closed: dict[tuple, list[tuple[int, int]]] = {}
    expansions = 0
    g = 0
    max_g = 0

    while g <= max_g or g in buckets:
        bucket = buckets.pop(g, None)
        if not bucket:
            g += 1
            continue

        while bucket:
            node = bucket.pop()
            state = node.state

            # Al extraer, no al generar: es lo que garantiza el óptimo.
            if problem.is_goal(state):
                return node

            key = _dominance_key(state)
            entries = closed.get(key)
            if entries is None:
                entries = []
                closed[key] = entries
            elif _is_dominated(entries, g, state.battery):
                continue  # ya se llegó a este mundo igual o mejor
            entries.append((g, state.battery))

            expansions += 1
            if expansions > expansion_limit:
                raise SearchLimitExceeded(
                    f"Se superó el límite de {expansion_limit} expansiones sin hallar meta."
                )
            if time_limit_s is not None and expansions % _TIME_CHECK_EVERY == 0:
                elapsed = time.monotonic() - started
                if elapsed > time_limit_s:
                    raise SearchLimitExceeded(
                        f"Se superó el límite de {time_limit_s:.0f} s de búsqueda "
                        f"({expansions} expansiones) sin hallar meta."
                    )

            for action, next_state, cost in successors(problem, state):
                child_g = g + cost
                # Solo para no encolar de más; el filtro que cuenta es el de arriba.
                child_entries = closed.get(_dominance_key(next_state))
                if child_entries and _is_dominated(
                    child_entries, child_g, next_state.battery
                ):
                    continue
                child = Node(next_state, node, action, child_g)
                target = buckets.get(child_g)
                if target is None:
                    buckets[child_g] = [child]
                else:
                    target.append(child)
                if child_g > max_g:
                    max_g = child_g
        g += 1

    return None  # OPEN vacía: no hay plan
