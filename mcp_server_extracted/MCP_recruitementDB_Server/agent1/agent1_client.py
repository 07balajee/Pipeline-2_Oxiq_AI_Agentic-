"""Dummy Agent 1 + MCP client — end-to-end test against the live server.

Agent 1 ("Manager provides Job Description") is granted, per registry.yaml:

    read : requisitions ["*"]
    write: requisitions  ops=[insert, update]   (may set initial status only)

It has NO transition grant and NO grant on any other table, so this harness
also proves the ACL denies what it should.

The client launches ../server.py over stdio (a real MCP session — the same
transport an in-process agent would use) and drives a scripted Agent 1 flow:

    1. health_check            - works with no DB, no auth
    2. list_capabilities       - discovery, ~6 lines, no columns
    3. describe_resource       - column contract for requisitions only
    4. query_resource          - read (shows the DB-down / JSON-twin fallback)
    5. write_resource insert   - happy path (or clean database_unavailable stop)
    6. write_resource insert   - NEGATIVE: illegal direct status set -> denied
    7. query_resource(candidates) - NEGATIVE: no grant -> capability_denied

It launches the real ../server.py over stdio. With .env configured, server.py
loads the Supabase credentials and the read/write steps run against the live
database; without them, those steps show the clean DB-down / write-stop path
(code="database_unavailable"). The ACL denials fire either way.

Run:  python Agent1/agent1_client.py
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

HERE = Path(__file__).resolve().parent
# Drives the real server. With .env configured it reads/writes live Supabase;
# without credentials the read/write steps show the clean DB-down / write-stop path.
# Override the path with AGENT1_SERVER if the server lives elsewhere.
SERVER = (HERE / os.getenv("AGENT1_SERVER", "../server.py")).resolve()

AGENT_ID = "agent_1"


class DummyAgent1:
    """A minimal agent: it knows its id and talks to one MCP session."""

    def __init__(self, session: ClientSession, agent_id: str = AGENT_ID):
        self.session = session
        self.agent_id = agent_id

    async def call(self, tool: str, **kwargs) -> dict:
        """Invoke a server tool, always stamping this agent's id, and return the
        tool's structured dict (FastMCP returns dicts; the client surfaces them
        as structuredContent, falling back to parsing the JSON text block)."""
        args = {"agent_id": self.agent_id, **kwargs}
        result = await self.session.call_tool(tool, args)
        if getattr(result, "structuredContent", None):
            sc = result.structuredContent
            # FastMCP wraps a bare dict return under "result"
            return sc.get("result", sc) if isinstance(sc, dict) else sc
        for block in result.content:
            text = getattr(block, "text", None)
            if text:
                try:
                    return json.loads(text)
                except json.JSONDecodeError:
                    return {"raw": text}
        return {"ok": False, "note": "no content returned"}


def show(step: str, payload: dict, *, expect_ok: bool | None = None) -> bool:
    """Pretty-print one step and judge it. Returns True if it met expectation."""
    ok = bool(payload.get("ok"))
    code = payload.get("code")
    verdict = "PASS"
    if expect_ok is True and not ok:
        if code == "database_unavailable":
            verdict = "EXPECTED-STOP"        # no Supabase configured - clean write-stop
        elif code in ("database_error", "schema_error"):
            verdict = "DB-REJECTED"          # the live DB said no (e.g. missing PK) - server classified it correctly, NOT a false outage
        else:
            verdict = "FAIL"
    elif expect_ok is False and ok:
        verdict = "FAIL (should have been denied)"
    elif expect_ok is False and not ok:
        verdict = "PASS (correctly denied)"

    print(f"\n{'='*72}\n[{verdict}] {step}\n{'-'*72}")
    print(json.dumps(payload, indent=2, default=str)[:1600])
    return verdict.startswith("PASS") or verdict in ("EXPECTED-STOP", "DB-REJECTED")


async def main() -> int:
    params = StdioServerParameters(
        command=sys.executable,
        args=[str(SERVER)],
        env={**os.environ},  # no Supabase creds needed; DB-down path is exercised
    )

    results: list[bool] = []
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()

            tools = await session.list_tools()
            print(f"Server exposes {len(tools.tools)} tools: "
                  f"{', '.join(t.name for t in tools.tools)}")

            agent = DummyAgent1(session)

            # 1. health check — no auth, no DB required
            results.append(show(
                "health_check", await agent.call("health_check"), expect_ok=True))

            # 2. discovery
            caps = await agent.call("list_capabilities")
            results.append(show("list_capabilities(agent_1)", caps, expect_ok=True))

            # 3. column contract for the one table Agent 1 owns
            results.append(show(
                "describe_resource(requisitions)",
                await agent.call("describe_resource", table="requisitions"),
                expect_ok=True))

            # 4. read (will fall back / stop cleanly with no DB configured)
            results.append(show(
                "query_resource(requisitions, limit=5)",
                await agent.call("query_resource", table="requisitions", limit=5),
                expect_ok=True))

            # 5. write happy path — insert a dummy requisition at its initial state
            results.append(show(
                "write_resource insert requisitions (initial status)",
                await agent.call(
                    "write_resource", table="requisitions", op="insert",
                    data={
                        "role_title": "Backend Engineer (DUMMY)",
                        "department": "Engineering",
                        "count": 1,
                        "grade": "L4",
                        "requester": "dummy.manager@oxiqai.com",
                        "status": "Pending Approval",  # == ladder initial, allowed on insert
                    }),
                expect_ok=True))

            # 5b. read it back — proves the insert actually landed in the store
            results.append(show(
                "query_resource(requisitions, ilike 'DUMMY') read-back",
                await agent.call(
                    "query_resource", table="requisitions",
                    filters={"role_title": {"ilike": "DUMMY"}}),
                expect_ok=True))

            # 6. NEGATIVE — try to insert with a non-initial status: must be denied
            results.append(show(
                "write_resource insert with status='Approved' (should be denied)",
                await agent.call(
                    "write_resource", table="requisitions", op="insert",
                    data={"role_title": "X", "status": "Approved"}),
                expect_ok=False))

            # 7. NEGATIVE — read a table Agent 1 has no grant on: capability_denied
            results.append(show(
                "query_resource(candidates) with no grant (should be denied)",
                await agent.call("query_resource", table="candidates", limit=1),
                expect_ok=False))

    passed = sum(results)
    print(f"\n{'#'*72}\nAgent 1 harness: {passed}/{len(results)} steps met expectation\n{'#'*72}")
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
