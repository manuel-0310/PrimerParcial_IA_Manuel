"""Entregable 3 — ejecuta toda la validación y resume el resultado por caso.

    python tests/run_all.py

Sin dependencias externas: cada módulo expone funciones `test_*` con asserts
planos, así que también se pueden correr con pytest o de uno en uno
(`python tests/test_case3_cost_vs_steps.py`).
"""

from __future__ import annotations

import importlib
import sys
import time
import traceback
from pathlib import Path
from typing import Any, Callable, List, Tuple

TESTS_DIR = Path(__file__).resolve().parent
if str(TESTS_DIR) not in sys.path:
    sys.path.insert(0, str(TESTS_DIR))

# Los cinco casos que exige el enunciado, más los tests de apoyo.
SUITES: List[Tuple[str, str]] = [
    ("CASO 1 — Estados equivalentes", "test_case1_equivalent_states"),
    ("CASO 2 — Información relevante", "test_case2_relevant_info"),
    ("CASO 3 — Costos ≠ número de acciones", "test_case3_cost_vs_steps"),
    ("CASO 4 — Sin solución (FAILURE)", "test_case4_failure"),
    ("CASO 5 — Rutas alternativas", "test_case5_alternative_routes"),
    ("Soporte — Política PICKUP/DROP", "test_actions_capacity"),
    ("Soporte — El agente resuelve la demo", "test_agent_solves_demo"),
    ("Base — Plan artesanal de referencia", "test_demo_plan"),
]

WIDTH = 46


def collect(module: Any) -> List[Callable[[], None]]:
    """La lista TESTS del módulo, o las funciones test_* si no la declara."""
    declared = getattr(module, "TESTS", None)
    if declared:
        return list(declared)
    return [
        value
        for name, value in vars(module).items()
        if name.startswith("test_") and callable(value)
    ]


def main() -> int:
    failures: List[Tuple[str, str, str]] = []
    started = time.time()

    print()
    print("Emergency Control — Entregable 3: validación")
    print("=" * (WIDTH + 16))

    for label, module_name in SUITES:
        try:
            module = importlib.import_module(module_name)
            tests = collect(module)
        except Exception:
            print(f"{label:.<{WIDTH}} ERROR AL IMPORTAR")
            failures.append((label, module_name, traceback.format_exc()))
            continue

        passed = 0
        local: List[Tuple[str, str]] = []
        for test in tests:
            try:
                test()
                passed += 1
            except Exception:
                local.append((test.__name__, traceback.format_exc()))

        status = "OK" if passed == len(tests) else f"{len(local)} FALLO(S)"
        print(f"{label:.<{WIDTH}} {passed}/{len(tests)} {status}")
        for test_name, tb in local:
            failures.append((label, test_name, tb))

    elapsed = time.time() - started
    print("=" * (WIDTH + 16))

    if failures:
        print(f"\n{len(failures)} fallo(s) en {elapsed:.1f}s:\n")
        for label, test_name, tb in failures:
            print(f"--- {label} :: {test_name} ---")
            print(tb)
        return 1

    print(f"\nTodo en verde — los 5 casos del Entregable 3 en {elapsed:.1f}s.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
