# Backend — Emergency Control

API en FastAPI que expone `POST /api/solve`. Recibe un escenario y devuelve el
plan de **menor costo** que satisface la meta, o `FAILURE` si no existe.

> Las instrucciones completas de instalación, ejecución e interpretación están
> en [`../README.md`](../README.md). Este archivo es solo una referencia rápida
> de la estructura interna.

## Módulos

| Archivo | Responsabilidad |
|---|---|
| `src/state.py` | Representación canónica del estado y las funciones de transición |
| `src/problem.py` | Constantes derivadas del escenario, estado inicial y prueba de meta |
| `src/actions.py` | `Applicable(s)` — generación de sucesores y política de `PICKUP`/`DROP` |
| `src/search.py` | UCS sobre Graph Search, con dominancia de batería en CLOSED |
| `src/translate.py` | Nodo meta → pasos del contrato cerrado (`CONTRATO.md` §3) |
| `src/main.py` | El endpoint |
| `src/simulator.py` | Re-simulador de referencia usado por los tests |
| `src/demo_plan.py` | Plan artesanal del repositorio base, conservado como referencia de costo |

El diseño que sustenta cada decisión está en [`../design.md`](../design.md).

## Ejecutar

```bash
cd project/backend
source .venv/bin/activate        # .\.venv\Scripts\activate en Windows
uvicorn main:app --app-dir src --port 8000
```

Añada `--reload` si va a editar el código.

## Tests

```bash
python tests/run_all.py
```

Los cinco casos del Entregable 3 más los tests de apoyo. Requiere el entorno
virtual activado. Ver [`../README.md`](../README.md#validación--entregable-3).
