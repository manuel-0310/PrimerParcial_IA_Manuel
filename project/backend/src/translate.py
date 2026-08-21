"""Nodo ganador -> steps del contrato (CONTRATO.md §3)."""

from __future__ import annotations

from typing import Any

from actions import Action
from search import Node


def _action_to_step(action: Action) -> dict[str, Any]:
    if action.kind == "move":
        return {
            "op": "MOVE",
            "from": action.zone_from,
            "to": action.zone_to,
            "cost": action.cost,
        }
    if action.kind in ("pickup_unique", "pickup_material"):
        return {"op": "PICKUP", "item": action.item, "cost": action.cost}
    if action.kind in ("drop_unique", "drop_material"):
        return {"op": "DROP", "item": action.item, "cost": action.cost}
    if action.kind == "open_door":
        return {
            "op": "INTERACT",
            "target": action.target,
            "action": "OPEN_DOOR",
            "cost": action.cost,
        }
    if action.kind == "repair":
        return {
            "op": "INTERACT",
            "target": action.target,
            "action": "REPAIR",
            "consumes": action.consumes,
            "cost": action.cost,
        }
    if action.kind == "activate":
        return {
            "op": "INTERACT",
            "target": action.target,
            "action": "ACTIVATE",
            "cost": action.cost,
        }
    if action.kind == "recharge":
        return {
            "op": "INTERACT",
            "target": action.target,
            "action": "RECHARGE",
            "cost": action.cost,
        }
    raise ValueError(f"Acción interna desconocida: {action.kind}")


def build_steps(goal_node: Node) -> list[dict[str, Any]]:
    actions: list[Action] = []
    node = goal_node
    while node.parent is not None:
        actions.append(node.action)
        node = node.parent
    actions.reverse()
    return [_action_to_step(a) for a in actions]
