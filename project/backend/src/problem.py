"""Constantes derivadas del escenario — ver project/design.md § "qué se deriva"."""

from __future__ import annotations

from typing import Any

from state import State, canonicalize


class Problem:
    def __init__(self, scenario: dict[str, Any]) -> None:
        self.scenario = scenario

        self.start_zone: str = scenario["robot"]["start"]
        self.battery_start: int = scenario["robot"]["battery_start"]
        self.battery_max: int = scenario["robot"]["battery_max"]
        self.cargo_capacity: int = scenario["robot"]["cargo_capacity"]
        self.action_costs: dict[str, int] = scenario["action_costs"]
        self.goal_stations: frozenset[str] = frozenset(scenario["goal"]["stations_online"])

        self.zones_by_id = {z["id"]: z for z in scenario["zones"]}
        self.doors_by_id = {d["id"]: d for d in scenario["doors"]}
        self.keys_by_id = {k["id"]: k for k in scenario["keys"]}
        self.tools_by_id = {t["id"]: t for t in scenario["tools"]}
        self.panels_by_id = {p["id"]: p for p in scenario["panels"]}
        self.stations_by_id = {s["id"]: s for s in scenario["stations"]}
        self.chargers_by_id = {c["id"]: c for c in scenario["chargers"]}

        # Sin asumir simetría: el escenario lista cada sentido por separado.
        self.corridors_from: dict[str, list[dict[str, Any]]] = {}
        self.corridors_by_pair: dict[tuple[str, str], dict[str, Any]] = {}
        for c in scenario["corridors"]:
            self.corridors_from.setdefault(c["from"], []).append(c)
            self.corridors_by_pair[(c["from"], c["to"])] = c

        # Orden alfabético fijo: es el índice de payload_materials en el estado.
        # Se incluyen los tipos que un panel requiere aunque no haya stock, para
        # que un escenario sin ese material dé FAILURE en vez de KeyError.
        material_types = {m["type"] for m in scenario["materials"]}
        material_types |= {p["requires"]["material"] for p in scenario["panels"]}
        self.material_types: tuple[str, ...] = tuple(sorted(material_types))
        self._material_weight: dict[str, int] = {}
        self._material_stacks: dict[str, list[tuple[str, int]]] = {}
        for m in scenario["materials"]:
            self._material_stacks.setdefault(m["type"], []).append((m["zone"], m["count"]))
            prev = self._material_weight.get(m["type"])
            if prev is not None and prev != m["weight"]:
                raise ValueError(
                    f"Material {m['type']} tiene pesos distintos entre stacks "
                    f"({prev} vs {m['weight']}) — no es fungible bajo ese supuesto."
                )
            self._material_weight[m["type"]] = m["weight"]

        self.key_to_door: dict[str, str] = {d["key"]: d["id"] for d in scenario["doors"]}

        # frozenset para comprobar "todos reparados" con <=.
        panels_by_tool: dict[str, set[str]] = {}
        panels_by_material: dict[str, set[str]] = {}
        for p in scenario["panels"]:
            panels_by_tool.setdefault(p["requires"]["tool"], set()).add(p["id"])
            panels_by_material.setdefault(p["requires"]["material"], set()).add(p["id"])
        self.panels_by_tool = {k: frozenset(v) for k, v in panels_by_tool.items()}
        self.panels_by_material = {k: frozenset(v) for k, v in panels_by_material.items()}

        # Precomputados: se consultan en cada expansión.
        self.item_kind: dict[str, str] = {}
        for key_id in self.keys_by_id:
            self.item_kind[key_id] = "key"
        for tool_id in self.tools_by_id:
            self.item_kind[tool_id] = "tool"
        for material_type in self.material_types:
            self.item_kind[material_type] = "material"
        self.material_index: dict[str, int] = {
            t: i for i, t in enumerate(self.material_types)
        }
        self._weights: dict[str, int] = {
            item_id: self._lookup_weight(item_id) for item_id in self.item_kind
        }
        self.uniform_weights: bool = set(self._weights.values()) <= {1}

        # RECHARGE necesita el id de un charger real, no basta zone.recharge:
        # el simulador resuelve el target contra scenario.chargers.
        self.chargers_by_zone: dict[str, str] = {}
        for c in scenario["chargers"]:
            self.chargers_by_zone[c["zone"]] = c["id"]
        for z in scenario["zones"]:
            if z.get("recharge") and z["id"] not in self.chargers_by_zone:
                raise ValueError(
                    f"Zona {z['id']} está marcada recharge=true pero no tiene "
                    "ningún charger en scenario.chargers — instancia inconsistente."
                )

    def _lookup_weight(self, item_id_or_type: str) -> int:
        if item_id_or_type in self.keys_by_id:
            return self.keys_by_id[item_id_or_type]["weight"]
        if item_id_or_type in self.tools_by_id:
            return self.tools_by_id[item_id_or_type]["weight"]
        # Un tipo sin stock no declara peso; nunca se recoge, el valor da igual.
        return self._material_weight.get(item_id_or_type, 1)

    def weight_of(self, item_id_or_type: str) -> int:
        return self._weights[item_id_or_type]

    def is_goal(self, state: State) -> bool:
        return self.goal_stations <= state.stations_online

    def initial_state(self) -> State:
        ground_unique = frozenset(
            (k["id"], k["zone"]) for k in self.scenario["keys"]
        ) | frozenset((t["id"], t["zone"]) for t in self.scenario["tools"])
        ground_materials = frozenset(
            (t, z, count) for t, stacks in self._material_stacks.items() for z, count in stacks
        )
        raw = State(
            zone=self.start_zone,
            battery=self.battery_start,
            payload_unique=frozenset(),
            payload_materials=tuple(0 for _ in self.material_types),
            ground_unique=ground_unique,
            ground_materials=ground_materials,
            doors_open=frozenset(
                d["id"] for d in self.scenario["doors"] if d["state"] == "OPEN"
            ),
            panels_repaired=frozenset(
                p["id"] for p in self.scenario["panels"] if p["state"] == "OK"
            ),
            stations_online=frozenset(
                s["id"] for s in self.scenario["stations"] if s["state"] == "ONLINE"
            ),
        )
        return canonicalize(self, raw)

    @classmethod
    def from_scenario(cls, scenario: dict[str, Any]) -> "Problem":
        return cls(scenario)
