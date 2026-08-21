"""Estado canónico de búsqueda y transiciones — ver design.md § Estado."""

from __future__ import annotations

from typing import NamedTuple


class State(NamedTuple):
    zone: str
    battery: int
    payload_unique: frozenset[str]
    payload_materials: tuple[int, ...]
    ground_unique: frozenset[tuple[str, str]]
    ground_materials: frozenset[tuple[str, str, int]]
    doors_open: frozenset[str]
    panels_repaired: frozenset[str]
    stations_online: frozenset[str]


def carried_weight(problem, state: State) -> int:
    if problem.uniform_weights:
        return len(state.payload_unique) + sum(state.payload_materials)
    weights = problem._weights
    total = sum(weights[item_id] for item_id in state.payload_unique)
    for material_type, count in zip(problem.material_types, state.payload_materials):
        total += count * weights[material_type]
    return total


def free_capacity(problem, state: State) -> int:
    return problem.cargo_capacity - carried_weight(problem, state)


def is_dead_key(problem, state: State, key_id: str) -> bool:
    door_id = problem.key_to_door[key_id]
    return door_id in state.doors_open


def is_dead_tool(problem, state: State, tool_id: str) -> bool:
    pending = problem.panels_by_tool.get(tool_id)
    return pending is None or pending <= state.panels_repaired


def pending_demand(problem, state: State, material_type: str) -> int:
    """Unidades de este material que aún hará falta consumir."""
    pending = problem.panels_by_material.get(material_type)
    if pending is None:
        return 0
    return len(pending - state.panels_repaired)


def is_dead_material(problem, state: State, material_type: str) -> bool:
    pending = problem.panels_by_material.get(material_type)
    return pending is None or pending <= state.panels_repaired


def has_enough_material(problem, state: State, material_type: str) -> bool:
    """Se cargan ya tantas unidades como paneles pendientes las piden.

    Cada REPAIR consume una, así que la siguiente unidad no habilita nada.
    """
    carried = state.payload_materials[material_index(problem, material_type)]
    return carried >= pending_demand(problem, state, material_type)


def is_dead(problem, state: State, item_id_or_type: str) -> bool:
    kind = problem.item_kind[item_id_or_type]
    if kind == "key":
        return problem.key_to_door[item_id_or_type] in state.doors_open
    if kind == "tool":
        return is_dead_tool(problem, state, item_id_or_type)
    return is_dead_material(problem, state, item_id_or_type)


def material_index(problem, material_type: str) -> int:
    return problem.material_index[material_type]


def canonicalize(problem, state: State) -> State:
    """Olvida en qué zona quedaron los objetos muertos del suelo.

    PICKUP no vuelve a generarlos, así que su posición ya no distingue estados
    y guardarla multiplicaría el espacio. Los del payload sí se conservan:
    siguen ocupando capacidad.
    """
    ground_unique = frozenset(
        (i, z) for (i, z) in state.ground_unique if not is_dead(problem, state, i)
    )
    ground_materials = frozenset(
        (t, z, c) for (t, z, c) in state.ground_materials if not is_dead(problem, state, t)
    )
    if ground_unique == state.ground_unique and ground_materials == state.ground_materials:
        return state
    return state._replace(ground_unique=ground_unique, ground_materials=ground_materials)


def apply_move(state: State, to_zone: str, cost: int) -> State:
    return state._replace(zone=to_zone, battery=state.battery - cost)


def apply_pickup_unique(state: State, item_id: str, cost: int) -> State:
    ground = frozenset(
        (i, z) for (i, z) in state.ground_unique if not (i == item_id and z == state.zone)
    )
    return state._replace(
        battery=state.battery - cost,
        payload_unique=state.payload_unique | {item_id},
        ground_unique=ground,
    )


def apply_drop_unique(state: State, item_id: str, cost: int) -> State:
    return state._replace(
        battery=state.battery - cost,
        payload_unique=state.payload_unique - {item_id},
        ground_unique=state.ground_unique | {(item_id, state.zone)},
    )


def apply_pickup_material(problem, state: State, material_type: str, cost: int) -> State:
    idx = material_index(problem, material_type)
    materials = list(state.payload_materials)
    materials[idx] += 1

    ground = list(state.ground_materials)
    for i, (t, z, count) in enumerate(ground):
        if t == material_type and z == state.zone:
            if count > 1:
                ground[i] = (t, z, count - 1)
            else:
                ground.pop(i)
            break

    return state._replace(
        battery=state.battery - cost,
        payload_materials=tuple(materials),
        ground_materials=frozenset(ground),
    )


def apply_drop_material(problem, state: State, material_type: str, cost: int) -> State:
    idx = material_index(problem, material_type)
    materials = list(state.payload_materials)
    materials[idx] -= 1

    ground = list(state.ground_materials)
    for i, (t, z, count) in enumerate(ground):
        if t == material_type and z == state.zone:
            ground[i] = (t, z, count + 1)
            break
    else:
        ground.append((material_type, state.zone, 1))

    return state._replace(
        battery=state.battery - cost,
        payload_materials=tuple(materials),
        ground_materials=frozenset(ground),
    )


def apply_open_door(problem, state: State, door_id: str, cost: int) -> State:
    return canonicalize(
        problem,
        state._replace(
            battery=state.battery - cost,
            doors_open=state.doors_open | {door_id},
        ),
    )


def apply_repair(problem, state: State, panel_id: str, material_type: str, cost: int) -> State:
    idx = material_index(problem, material_type)
    materials = list(state.payload_materials)
    materials[idx] -= 1
    return canonicalize(
        problem,
        state._replace(
            battery=state.battery - cost,
            payload_materials=tuple(materials),
            panels_repaired=state.panels_repaired | {panel_id},
        ),
    )


def apply_activate(state: State, station_id: str, cost: int) -> State:
    return state._replace(
        battery=state.battery - cost,
        stations_online=state.stations_online | {station_id},
    )


def apply_recharge(problem, state: State) -> State:
    # El costo solo se exige como precondición; no se resta del resultado.
    return state._replace(battery=problem.battery_max)
