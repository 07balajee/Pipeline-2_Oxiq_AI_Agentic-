"""Diff registry.yaml against the live Supabase schema.

The registry's column lists were transcribed from a mapping document, not read
out of Postgres. Any drift - a renamed column, a table that isn't there, a
column an agent is granted but that doesn't exist - would otherwise only surface
at runtime, inside an agent, mid-pipeline.

Run it before wiring in any agent, and in CI:

    python validate_registry.py            # human-readable
    python validate_registry.py --json     # machine-readable
    python validate_registry.py --strict   # exit 1 on warnings too

Exit codes: 0 clean, 1 errors found, 2 could not reach the database.

Best results come from deploying the table_columns() helper in
sql/atomic_helpers.sql - without it, empty tables can't be introspected and are
reported as "unverified" rather than passing silently.
"""

from __future__ import annotations

import json
import sys

import db
from errors import McpError
from registry import load_registry


def validate() -> dict:
    reg = load_registry()
    errors: list[str] = []
    warnings: list[str] = []
    unverified: list[str] = []
    checked: dict[str, int] = {}

    live: dict[str, list[str] | None] = {}
    for table in reg.tables:
        try:
            cols = db.live_columns(table)
        except McpError as exc:
            return {
                "ok": False,
                "reachable": False,
                "message": f"Could not reach the database: {exc.message}",
            }
        live[table] = cols
        if cols is None:
            unverified.append(table)
        else:
            checked[table] = len(cols)

    # 1. every registry table exists, and its PK is a real column
    for name, spec in reg.tables.items():
        cols = live.get(name)
        if cols is None:
            continue
        if not cols:
            errors.append(f"table {name!r} returned no columns - does it exist?")
            continue
        if spec.pk not in cols:
            errors.append(f"{name}: primary key {spec.pk!r} is not a column (live: {cols})")
        for arr in spec.json_arrays:
            if arr not in cols:
                errors.append(f"{name}: json_arrays lists {arr!r}, which is not a column")

    # 2. every granted column exists
    for agent_id, grant in reg.agents.items():
        for table, cols in (grant.get("read") or {}).items():
            if table not in reg.tables:
                errors.append(f"{agent_id}: reads unknown table {table!r}")
                continue
            actual = live.get(table)
            if actual is None or cols == ["*"]:
                continue
            missing = [c for c in cols if c not in actual]
            if missing:
                errors.append(f"{agent_id}: read grant on {table} names missing columns {missing}")

        for table, spec in (grant.get("write") or {}).items():
            if table not in reg.tables:
                errors.append(f"{agent_id}: writes unknown table {table!r}")
                continue
            actual = live.get(table)
            declared = spec.get("columns") or []
            if actual is not None and declared and declared != ["*"]:
                missing = [c for c in declared if c not in actual]
                if missing:
                    errors.append(
                        f"{agent_id}: write grant on {table} names missing columns {missing}"
                    )
            for op in spec.get("ops") or []:
                if op not in ("insert", "update", "upsert", "append_json", "transition",
                              "cascade", "delete"):
                    errors.append(f"{agent_id}: unknown operation {op!r} on {table}")
            if "delete" in (spec.get("ops") or []):
                warnings.append(f"{agent_id} holds a DELETE grant on {table} - is that intended?")
            if "append_json" in (spec.get("ops") or []):
                appendable = reg.tables[table].json_arrays
                bad = [c for c in declared if c not in appendable] if declared else []
                if bad:
                    warnings.append(
                        f"{agent_id}: append_json on {table} but {bad} are not json_arrays"
                    )

    # 3. status ladders point at real columns and are internally closed
    for entity, ladder in reg.transitions.items():
        if entity not in reg.tables:
            errors.append(f"transition ladder {entity!r} has no table entry")
            continue
        actual = live.get(entity)
        if actual is not None and ladder.column not in actual:
            errors.append(f"{entity}: status column {ladder.column!r} does not exist")
        states = set(ladder.map)
        for state, targets in ladder.map.items():
            for target in targets:
                if target not in states:
                    errors.append(
                        f"{entity}: {state} -> {target} but {target!r} has no entry of its own"
                    )
        if ladder.initial and ladder.initial not in states:
            errors.append(f"{entity}: initial state {ladder.initial!r} is not in the ladder")

    # 4. agents that can hand over must agree on the target states
    for agent_id, grant in reg.agents.items():
        for table, spec in (grant.get("write") or {}).items():
            allowed = spec.get("statuses")
            if not allowed:
                continue
            ladder = reg.transitions.get(table)
            if ladder is None:
                errors.append(f"{agent_id}: statuses declared on {table}, which has no ladder")
                continue
            known = {s for targets in ladder.map.values() for s in targets} | set(ladder.map)
            unknown = [s for s in allowed if s not in known]
            if unknown:
                errors.append(f"{agent_id}: may_set lists states not in the {table} ladder: {unknown}")

    return {
        "ok": not errors,
        "reachable": True,
        "errors": errors,
        "warnings": warnings,
        "unverified_tables": unverified,
        "verified_tables": checked,
        "agents": len(reg.agents),
    }


def main() -> int:
    as_json = "--json" in sys.argv
    strict = "--strict" in sys.argv
    report = validate()

    if as_json:
        print(json.dumps(report, indent=2))
    else:
        if not report.get("reachable"):
            print(f"UNREACHABLE  {report.get('message')}")
            return 2
        for err in report["errors"]:
            print(f"ERROR    {err}")
        for warn in report["warnings"]:
            print(f"WARNING  {warn}")
        for table in report["unverified_tables"]:
            print(f"SKIPPED  {table} - empty and no table_columns() helper; could not verify")
        print(
            f"\n{len(report['verified_tables'])} tables verified, "
            f"{len(report['errors'])} errors, {len(report['warnings'])} warnings."
        )
        if report["ok"] and not report["errors"]:
            print("Registry matches the live schema.")

    if not report.get("reachable"):
        return 2
    if report["errors"]:
        return 1
    if strict and report["warnings"]:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
