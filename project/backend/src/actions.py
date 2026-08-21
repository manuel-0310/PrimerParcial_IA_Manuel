"""Applicable(s) y generación de sucesores — ver project/design.md § Acciones."""

from __future__ import annotations

from typing import NamedTuple

import state as st
from state import State


class Action(NamedTuple):
    kind: str  # move | pickup_unique | pickup_material | drop_unique | drop_material
    # | open_door | repair | activate | recharge
    zone_from: str = ""
    zone_to: str = ""
    item: str = ""  # id único o tipo de material (pickup/drop)
    target: str = ""  # id de puerta/panel/estación/charger (INTERACT)
    consumes: str = ""  # tipo de material (REPAIR)
    cost: int = 0


def _items_in_zone(problem, state: State, zone: str) -> list[str]:
    unique = [item_id for (item_id, z) in state.ground_unique if z == zone]
    materials = [
        t for (t, z, count) in state.ground_materials if z == zone and count > 0
    ]
    return unique + materials


def _is_material(problem, item_id_or_type: str) -> bool:
    return item_id_or_type not in problem.keys_by_id and item_id_or_type not in problem.tools_by_id


def _is_relevant_pickup(problem, state: State, item: str) -> bool:
    """Recogerlo puede habilitar alguna acción futura."""
    if st.is_dead(problem, state, item):
        return False
    if _is_material(problem, item) and st.has_enough_material(problem, state, item):
        return False
    return True


def _successors_move(problem, state: State) -> list[tuple[Action, State, int]]:
    out = []
    for corridor in problem.corridors_from.get(state.zone, []):
        door_id = corridor.get("door")
        if door_id and door_id not in state.doors_open:
            continue
        cost = int(corridor["cost"])
        if state.battery < cost:
            continue
        action = Action(kind="move", zone_from=state.zone, zone_to=corridor["to"], cost=cost)
        out.append((action, st.apply_move(state, corridor["to"], cost), cost))
    return out


def _successors_pickup(
    problem, state: State, relevant: list[str], free: int
) -> list[tuple[Action, State, int]]:
    out = []
    cost = int(problem.action_costs["pickup"])
    if state.battery < cost:
        return out
    for item in relevant:
        if problem.weight_of(item) > free:
            continue
        if _is_material(problem, item):
            action = Action(kind="pickup_material", item=item, cost=cost)
            next_state = st.apply_pickup_material(problem, state, item, cost)
        else:
            action = Action(kind="pickup_unique", item=item, cost=cost)
            next_state = st.apply_pickup_unique(state, item, cost)
        out.append((action, next_state, cost))
    return out


def _blocked_pickup_exists(problem, state: State, relevant: list[str], free: int) -> bool:
    """Hay algo que recoger aquí que cabría en el robot vacío pero no ahora."""
    capacity = problem.cargo_capacity
    for item in relevant:
        w = problem.weight_of(item)
        if free < w <= capacity:
            return True
    return False


def _successors_drop(
    problem, state: State, relevant: list[str], free: int
) -> list[tuple[Action, State, int]]:
    """DROP solo cuando falta hueco, y siempre en la zona actual.

    Generar cualquier DROP legal haría que el espacio de estados fuera "en qué
    zona quedó cada objeto" y UCS no terminaría. Si hay algo muerto encima se
    suelta eso: nunca habrá que volver a recogerlo.
    """
    out = []
    cost = int(problem.action_costs["drop"])
    if state.battery < cost or not _blocked_pickup_exists(problem, state, relevant, free):
        return out

    dead_unique = [i for i in state.payload_unique if st.is_dead(problem, state, i)]
    dead_materials = [
        problem.material_types[i]
        for i, c in enumerate(state.payload_materials)
        if c > 0 and st.is_dead(problem, state, problem.material_types[i])
    ]
    if dead_unique or dead_materials:
        candidates_unique, candidates_materials = dead_unique, dead_materials
    else:
        candidates_unique = list(state.payload_unique)
        candidates_materials = [
            problem.material_types[i] for i, c in enumerate(state.payload_materials) if c > 0
        ]

    for item in candidates_unique:
        action = Action(kind="drop_unique", item=item, cost=cost)
        next_state = st.canonicalize(problem, st.apply_drop_unique(state, item, cost))
        out.append((action, next_state, cost))
    for item in candidates_materials:
        action = Action(kind="drop_material", item=item, cost=cost)
        next_state = st.canonicalize(problem, st.apply_drop_material(problem, state, item, cost))
        out.append((action, next_state, cost))
    return out


def _successors_open_door(problem, state: State) -> list[tuple[Action, State, int]]:
    out = []
    cost = int(problem.action_costs["interact"])
    if state.battery < cost:
        return out
    for door_id, door in problem.doors_by_id.items():
        if door_id in state.doors_open:
            continue
        if state.zone not in door["between"]:
            continue
        if door["key"] not in state.payload_unique:
            continue
        action = Action(kind="open_door", target=door_id, cost=cost)
        out.append((action, st.apply_open_door(problem, state, door_id, cost), cost))
    return out


def _successors_repair(problem, state: State) -> list[tuple[Action, State, int]]:
    out = []
    cost = int(problem.action_costs["interact"])
    if state.battery < cost:
        return out
    for panel_id, panel in problem.panels_by_id.items():
        if panel_id in state.panels_repaired:
            continue
        if panel["zone"] != state.zone:
            continue
        tool = panel["requires"]["tool"]
        material = panel["requires"]["material"]
        if tool not in state.payload_unique:
            continue
        midx = st.material_index(problem, material)
        if state.payload_materials[midx] < 1:
            continue
        action = Action(kind="repair", target=panel_id, consumes=material, cost=cost)
        out.append((action, st.apply_repair(problem, state, panel_id, material, cost), cost))
    return out


def _successors_activate(problem, state: State) -> list[tuple[Action, State, int]]:
    out = []
    cost = int(problem.action_costs["interact"])
    if state.battery < cost:
        return out
    for station_id, station in problem.stations_by_id.items():
        if station_id in state.stations_online:
            continue
        if station["zone"] != state.zone:
            continue
        requires = station["requires"]
        if not all(p in state.panels_repaired for p in requires.get("panels_ok", [])):
            continue
        if not all(s in state.stations_online for s in requires.get("stations_online", [])):
            continue
        action = Action(kind="activate", target=station_id, cost=cost)
        out.append((action, st.apply_activate(state, station_id, cost), cost))
    return out


def _successors_recharge(problem, state: State) -> list[tuple[Action, State, int]]:
    charger_id = problem.chargers_by_zone.get(state.zone)
    if charger_id is None or state.battery >= problem.battery_max:
        return []
    cost = int(problem.action_costs["recharge"])
    if state.battery < cost:
        return []
    action = Action(kind="recharge", target=charger_id, cost=cost)
    return [(action, st.apply_recharge(problem, state), cost)]


def successors(problem, state: State) -> list[tuple[Action, State, int]]:
    # PICKUP y DROP usan ambos estas dos cosas: se calculan una vez.
    relevant = [
        item
        for item in _items_in_zone(problem, state, state.zone)
        if _is_relevant_pickup(problem, state, item)
    ]
    free = st.free_capacity(problem, state)
    out: list[tuple[Action, State, int]] = []
    out.extend(_successors_move(problem, state))
    out.extend(_successors_pickup(problem, state, relevant, free))
    out.extend(_successors_drop(problem, state, relevant, free))
    out.extend(_successors_open_door(problem, state))
    out.extend(_successors_repair(problem, state))
    out.extend(_successors_activate(problem, state))
    out.extend(_successors_recharge(problem, state))
    return out
