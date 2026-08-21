"""Escenarios sintéticos y helpers compartidos por los tests.

Son dicts de Python y no JSON en scenarios/ porque el agente no lee la clave
`layout`, pero el frontend sí: un JSON sin geometría rompería la escena 3D si
alguien lo abriera por error.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from problem import Problem  # noqa: E402
from search import solve  # noqa: E402
from simulator import load_scenario  # noqa: E402
from translate import build_steps  # noqa: E402

# Los mismos del escenario demo, para leer los costos con el mismo baremo.
ACTION_COSTS = {"pickup": 1, "drop": 1, "interact": 2, "recharge": 3}


def _corridor_pair(a: str, b: str, cost: int) -> List[Dict[str, Any]]:
    """Corredor en los dos sentidos, como los lista el escenario."""
    return [
        {"from": a, "to": b, "cost": cost, "door": None},
        {"from": b, "to": a, "cost": cost, "door": None},
    ]


def _base_scenario(
    zones: List[str],
    corridors: List[Dict[str, Any]],
    goal_zone: str,
    start: str = "Z1",
    battery_start: int = 100,
    battery_max: int = 100,
) -> Dict[str, Any]:
    """Una estación sin requisitos en `goal_zone` y nada más.

    Sin objetos que recoger el agente solo genera MOVE y ACTIVATE, así que lo
    único que se mide es la topología.
    """
    return {
        "robot": {
            "start": start,
            "battery_max": battery_max,
            "battery_start": battery_start,
            "cargo_capacity": 3,
        },
        "zones": [{"id": z, "name": z, "recharge": False} for z in zones],
        "corridors": corridors,
        "doors": [],
        "keys": [],
        "tools": [],
        "materials": [],
        "panels": [],
        "stations": [
            {
                "id": "ST",
                "kind": "generator",
                "zone": goal_zone,
                "state": "OFFLINE",
                "requires": {},
            }
        ],
        "chargers": [],
        "goal": {"stations_online": ["ST"]},
        "action_costs": dict(ACTION_COSTS),
    }


def cost_vs_steps_scenario() -> Dict[str, Any]:
    """Caso 3 — el plan más corto NO es el más barato.

        Z1 --------- 20 --------- ZG        ruta directa:  1 MOVE,  costo 20
         \\                        /
          3                      3          ruta larga:    2 MOVE,  costo  6
           \\                    /
            ----- ZM ----------

    Con ACTIVATE (2) encima:
      - menos acciones : MOVE Z1->ZG, ACTIVATE            = 2 pasos, costo 22
      - menor costo    : MOVE Z1->ZM, MOVE ZM->ZG, ACTIVATE = 3 pasos, costo  8

    UCS devuelve el de 3 pasos; BFS devolvería el de 2.
    """
    corridors = (
        _corridor_pair("Z1", "ZG", 20)
        + _corridor_pair("Z1", "ZM", 3)
        + _corridor_pair("ZM", "ZG", 3)
    )
    return _base_scenario(["Z1", "ZM", "ZG"], corridors, goal_zone="ZG")


def alternative_routes_scenario() -> Dict[str, Any]:
    """Caso 5 — dos rutas alternativas al mismo mundo, mismo número de acciones.

              ZA                    ruta A: Z1->ZA->ZG = 4 + 4 = 8
            4/  \\4
        Z1          ZG              ruta B: Z1->ZB->ZG = 2 + 3 = 5
            2\\  /3
              ZB

    Ambas son 2 MOVE, así que solo decide el costo. Óptimo: 7 por ZB.
    """
    corridors = (
        _corridor_pair("Z1", "ZA", 4)
        + _corridor_pair("ZA", "ZG", 4)
        + _corridor_pair("Z1", "ZB", 2)
        + _corridor_pair("ZB", "ZG", 3)
    )
    return _base_scenario(["Z1", "ZA", "ZB", "ZG"], corridors, goal_zone="ZG")


def tied_routes_scenario() -> Dict[str, Any]:
    """Caso 5 (empate) — las dos rutas cuestan lo mismo (5)."""
    corridors = (
        _corridor_pair("Z1", "ZA", 3)
        + _corridor_pair("ZA", "ZG", 2)
        + _corridor_pair("Z1", "ZB", 2)
        + _corridor_pair("ZB", "ZG", 3)
    )
    return _base_scenario(["Z1", "ZA", "ZB", "ZG"], corridors, goal_zone="ZG")


def battery_starved_scenario() -> Dict[str, Any]:
    """Caso 4 — FAILURE por recurso, no por topología.

    ZG está a un corredor de costo 10, pero el robot arranca con 5 de batería
    y no hay chargers.
    """
    return _base_scenario(
        ["Z1", "ZG"],
        _corridor_pair("Z1", "ZG", 10),
        goal_zone="ZG",
        battery_start=5,
    )


def unreachable_station_scenario() -> Dict[str, Any]:
    """Caso 4 — FAILURE por topología, con el espacio de estados agotable.

    ZISLA no tiene corredores, así que ISOLATED nunca llega a ONLINE.

    Se usa una instancia pequeña a propósito: sobre el escenario demo una meta
    imposible agota el presupuesto antes que OPEN, y aquí lo que se quiere
    demostrar es el FAILURE por espacio agotado.
    """
    scenario = _base_scenario(
        ["Z1", "ZG", "ZISLA"],
        _corridor_pair("Z1", "ZG", 3),
        goal_zone="ZG",
    )
    scenario["stations"].append(
        {
            "id": "ISOLATED",
            "kind": "generator",
            "zone": "ZISLA",
            "state": "OFFLINE",
            "requires": {},
        }
    )
    scenario["goal"]["stations_online"].append("ISOLATED")
    return scenario


# ── helpers ──────────────────────────────────────────────────────────────────


def solve_scenario(scenario: Dict[str, Any]) -> Tuple[List[Dict[str, Any]], int]:
    """(steps del contrato, costo total). Falla si no hay plan."""
    goal_node = solve(Problem.from_scenario(scenario))
    assert goal_node is not None, "se esperaba un plan, el agente devolvió FAILURE"
    steps = build_steps(goal_node)
    return steps, sum(int(s["cost"]) for s in steps)


def zones_visited(steps: List[Dict[str, Any]]) -> List[str]:
    """Zonas por las que pasa el plan, leídas de sus MOVE."""
    zones: List[str] = []
    for step in steps:
        if step["op"] != "MOVE":
            continue
        if not zones:
            zones.append(step["from"])
        zones.append(step["to"])
    return zones


_DEMO_CACHE: Optional[Tuple[Dict[str, Any], List[Dict[str, Any]]]] = None


def demo_agent_plan() -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
    """(escenario demo, plan del agente). Cacheado: la búsqueda tarda ~35 s."""
    global _DEMO_CACHE
    if _DEMO_CACHE is None:
        scenario = load_scenario()
        steps, _ = solve_scenario(scenario)
        _DEMO_CACHE = (scenario, steps)
    return _DEMO_CACHE


def demo_problem() -> Problem:
    """Problem del escenario demo, sin resolverlo."""
    return Problem.from_scenario(load_scenario())
