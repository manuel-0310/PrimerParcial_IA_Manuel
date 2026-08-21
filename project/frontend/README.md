# Frontend — Emergency Control

Escena voxel en React + TypeScript + Vite + React Three Fiber. Pide el plan a
`POST /api/solve` y lo **re-simula** paso a paso aplicando las reglas del mundo:
no confía en el plan recibido, así que si violara una precondición la ejecución
se detendría con un error en el registro.

> Las instrucciones completas de instalación, ejecución e interpretación de la
> interfaz están en [`../README.md`](../README.md).

## Ejecutar

```bash
cd project/frontend
npm install
npm run dev
```

Abrir <http://localhost:5173>. El proxy de Vite redirige `/api/*` al backend del
puerto 8000, que **debe estar corriendo**.

## Estructura

| Ruta | Contenido |
|---|---|
| `src/scene/` | Escena 3D: mundo, robot, entidades, confeti, efectos |
| `src/ui/HUD.tsx` | Paneles de batería, carga, costo, registro y controles |
| `src/lib/executor.ts` | Re-simulación de las reglas del mundo paso a paso |
| `src/lib/api.ts` | Llamada a `/api/solve` y reproducción del plan |
| `src/store/simStore.ts` | Estado de la simulación (zustand) |

El escenario se importa en tiempo de compilación desde
`../scenarios/scenario.json` mediante el alias `@scenario` (ver `vite.config.ts`).
