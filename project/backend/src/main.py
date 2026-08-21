"""API del agente: POST /api/solve devuelve el plan de menor costo."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from problem import Problem
from search import SearchLimitExceeded, solve as run_search
from translate import build_steps

app = FastAPI(title="Emergency Control API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

SCENARIO_PATH = Path(__file__).resolve().parents[2] / "scenarios" / "scenario.json"


def _load_default_scenario() -> dict[str, Any]:
    with SCENARIO_PATH.open(encoding="utf-8") as f:
        return json.load(f)


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/scenario")
def get_scenario() -> dict[str, Any]:
    return _load_default_scenario()


@app.post("/api/solve")
def solve(scenario: dict[str, Any]) -> dict[str, Any]:
    """Resuelve el escenario recibido. Formato de respuesta en CONTRATO.md §2."""
    data = scenario if scenario else _load_default_scenario()
    problem = Problem.from_scenario(data)

    try:
        goal_node = run_search(problem)
    except SearchLimitExceeded as exc:
        # No es el FAILURE del enunciado: no se llegó a determinar si hay plan.
        return {
            "solution_found": False,
            "total_cost": 0,
            "steps": [],
            "message": (
                f"Búsqueda detenida por presupuesto ({exc}) — no se pudo determinar "
                "si existe plan. No equivale a FAILURE."
            ),
        }

    if goal_node is None:
        return {
            "solution_found": False,
            "total_cost": 0,
            "steps": [],
            "message": "No existe un plan válido para esta misión (FAILURE).",
        }

    steps = build_steps(goal_node)
    total_cost = sum(int(s["cost"]) for s in steps)
    return {
        "solution_found": True,
        "total_cost": total_cost,
        "steps": steps,
        "message": "Plan generado por UCS (Graph Search con dominancia de batería).",
    }
