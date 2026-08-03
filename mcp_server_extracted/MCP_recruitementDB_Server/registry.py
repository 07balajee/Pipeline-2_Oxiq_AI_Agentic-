"""Capability registry: loads registry.yaml and answers every authorisation
question the server asks.

This module is the reason the tool surface is constant. Tables are DATA here,
not tool definitions, so an agent's context holds 7 tool schemas whether the DB
has 16 tables or 160.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Any

import yaml

from errors import CapabilityError, SchemaError, TransitionError

REGISTRY_PATH = os.getenv(
    "REGISTRY_PATH",
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "registry.yaml"),
)

WRITE_OPS = {"insert", "update", "upsert", "append_json"}
DESTRUCTIVE_OPS = {"delete"}
ALL_OPS = WRITE_OPS | DESTRUCTIVE_OPS | {"transition", "cascade"}


@dataclass
class TableSpec:
    name: str
    pk: str
    purpose: str
    json_fallback: str | None = None
    json_arrays: list[str] = field(default_factory=list)


@dataclass
class TransitionSpec:
    entity: str
    column: str
    initial: str
    map: dict[str, list[str]]

    def legal_from(self, current: str | None) -> list[str]:
        if current is None:
            return [self.initial]
        return self.map.get(current, [])

    def validate(self, current: str | None, target: str) -> None:
        legal = self.legal_from(current)
        if target not in legal:
            raise TransitionError(
                f"{self.entity}.{self.column} cannot move from "
                f"{current!r} to {target!r}.",
                hint=(
                    f"Legal targets from {current!r}: {legal or 'none - this is a terminal state'}."
                ),
                current=current,
                attempted=target,
                legal_targets=legal,
            )


class Registry:
    def __init__(self, raw: dict):
        self.version = raw.get("version", 1)
        self.tables: dict[str, TableSpec] = {
            name: TableSpec(
                name=name,
                pk=spec.get("pk", "id"),
                purpose=spec.get("purpose", ""),
                json_fallback=spec.get("json_fallback"),
                json_arrays=spec.get("json_arrays") or [],
            )
            for name, spec in (raw.get("tables") or {}).items()
        }
        self.transitions: dict[str, TransitionSpec] = {
            entity: TransitionSpec(
                entity=entity,
                column=spec.get("column", "status"),
                initial=spec.get("initial", ""),
                map=spec.get("map") or {},
            )
            for entity, spec in (raw.get("transitions") or {}).items()
        }
        self.agents: dict[str, dict] = raw.get("agents") or {}

    # ---------------------------------------------------------------- lookups

    def agent(self, agent_id: str) -> dict:
        grant = self.agents.get(agent_id)
        if grant is None:
            raise CapabilityError(
                f"Unknown agent_id {agent_id!r}.",
                hint=f"Known agents: {', '.join(sorted(self.agents))}.",
            )
        return grant

    def table(self, name: str) -> TableSpec:
        spec = self.tables.get(name)
        if spec is None:
            raise SchemaError(
                f"Unknown table {name!r}.",
                hint="Call list_capabilities to see the tables you may use.",
            )
        return spec

    # ------------------------------------------------------- the ACL question

    def capabilities(self, agent_id: str) -> dict:
        """The compact answer to 'is there a tool for this table?'.

        Deliberately omits column lists - that is describe_resource's job. This
        keeps the discovery payload at roughly 5-8 lines per agent.
        """
        grant = self.agent(agent_id)
        entries = []
        for table, cols in (grant.get("read") or {}).items():
            entries.append({"table": table, "ops": ["read"]})
        for table, spec in (grant.get("write") or {}).items():
            existing = next((e for e in entries if e["table"] == table), None)
            ops = list(spec.get("ops") or [])
            if existing:
                existing["ops"] += ops
            else:
                entries.append({"table": table, "ops": ops})

        for entry in entries:
            spec = self.tables.get(entry["table"])
            entry["purpose"] = spec.purpose if spec else ""
            if "transition" in entry["ops"]:
                t = self.transitions.get(entry["table"])
                allowed = ((grant.get("write") or {}).get(entry["table"]) or {}).get("statuses")
                if t:
                    entry["status_column"] = t.column
                    entry["may_set"] = allowed or sorted(
                        {s for targets in t.map.values() for s in targets}
                    )
        return {
            "ok": True,
            "agent_id": agent_id,
            "agent_name": grant.get("name", agent_id),
            "resources": entries,
            "note": (
                "Use describe_resource(table) for columns before writing. "
                "Status columns are written with transition_status, not write_resource."
            ),
        }

    def authorize_read(self, agent_id: str, table: str, columns: list[str] | None) -> list[str] | None:
        grant = self.agent(agent_id)
        allowed = (grant.get("read") or {}).get(table)
        if allowed is None:
            raise CapabilityError(
                f"Agent {agent_id!r} has no read grant on {table!r}.",
                hint="Call list_capabilities to see what this agent may read.",
                readable=sorted((grant.get("read") or {}).keys()),
            )
        if allowed == ["*"]:
            return columns
        if columns:
            bad = [c for c in columns if c not in allowed]
            if bad:
                raise SchemaError(
                    f"Agent {agent_id!r} may not read {bad} on {table!r}.",
                    hint=f"Readable columns: {allowed}.",
                )
            return columns
        return allowed

    def authorize_write(
        self,
        agent_id: str,
        table: str,
        op: str,
        columns: list[str],
        values: dict | None = None,
    ) -> None:
        grant = self.agent(agent_id)
        spec = (grant.get("write") or {}).get(table)
        if spec is None:
            raise CapabilityError(
                f"Agent {agent_id!r} has no write grant on {table!r}.",
                hint="Call list_capabilities to see what this agent may write.",
                writable=sorted((grant.get("write") or {}).keys()),
            )
        if op not in (spec.get("ops") or []):
            raise CapabilityError(
                f"Agent {agent_id!r} may not perform {op!r} on {table!r}.",
                hint=f"Allowed operations on {table!r}: {spec.get('ops')}.",
            )

        allowed_cols = spec.get("columns")
        if allowed_cols and allowed_cols != ["*"]:
            bad = [c for c in columns if c not in allowed_cols]
            if bad:
                raise SchemaError(
                    f"Agent {agent_id!r} may not write {bad} on {table!r}.",
                    hint=f"Writable columns: {allowed_cols}.",
                )

        # A status ladder may never be edited through a plain data write.
        # Exception: an INSERT may set the ladder's initial state, because a row
        # has to be born somewhere (candidates 'Applied', interviews 'Scheduled').
        t = self.transitions.get(table)
        if t and t.column in columns and op in WRITE_OPS:
            proposed = (values or {}).get(t.column)
            if op == "insert" and t.initial and proposed == t.initial:
                return
            raise CapabilityError(
                f"{table}.{t.column} is a managed status column.",
                hint=(
                    f"Use transition_status(entity={table!r}, ...) instead. "
                    f"An insert may only set the initial state {t.initial!r}."
                ),
                attempted=proposed,
                initial_state=t.initial,
            )

    def authorize_transition(self, agent_id: str, entity: str, target: str) -> TransitionSpec:
        grant = self.agent(agent_id)
        spec = (grant.get("write") or {}).get(entity)
        if spec is None or "transition" not in (spec.get("ops") or []):
            raise CapabilityError(
                f"Agent {agent_id!r} may not change {entity!r} status.",
                hint="Call list_capabilities to see this agent's transition grants.",
            )
        allowed = spec.get("statuses")
        if allowed and target not in allowed:
            raise CapabilityError(
                f"Agent {agent_id!r} may not set {entity}.status to {target!r}.",
                hint=f"This agent may set: {allowed}.",
            )
        t = self.transitions.get(entity)
        if t is None:
            raise SchemaError(f"No transition ladder defined for {entity!r}.")
        return t

    def authorize_cascade(self, agent_id: str) -> None:
        grant = self.agent(agent_id)
        spec = (grant.get("write") or {}).get("offer_links") or {}
        if "cascade" not in (spec.get("ops") or []):
            raise CapabilityError(
                f"Agent {agent_id!r} may not record offer responses.",
                hint="Only the agent holding the 'cascade' grant on offer_links may call this.",
            )


@lru_cache(maxsize=1)
def load_registry() -> Registry:
    with open(REGISTRY_PATH, "r", encoding="utf-8") as fh:
        return Registry(yaml.safe_load(fh))


def reload_registry() -> Registry:
    load_registry.cache_clear()
    return load_registry()
