"""Test suite for the recruitment MCP server.

Run:  python -m unittest discover -s tests -v
      (or: python tests/test_all.py)

No network and no database required - the db layer runs against an in-memory
fake so the real filter, retry, fallback and cascade code paths are exercised.
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ.setdefault("SUPABASE_URL", "https://test.supabase.co")
os.environ.setdefault("SUPABASE_SERVICE_KEY", "test-key")
os.environ["DB_BACKOFF_SECONDS"] = "0"

import auth  # noqa: E402
import cascade  # noqa: E402
import db  # noqa: E402
import filters as filt  # noqa: E402
from errors import (  # noqa: E402
    CapabilityError,
    DatabaseDownError,
    DatabaseError,
    McpError,
    SchemaError,
    TransitionError,
)
from registry import load_registry  # noqa: E402
from tests.fake_supabase import FailingStepClient, FakeClient, FlakyClient  # noqa: E402


def use(client):
    db.get_client = lambda: client
    return client


class RegistryAclTests(unittest.TestCase):
    def setUp(self):
        self.reg = load_registry()

    def test_registry_shape(self):
        self.assertEqual(len(self.reg.agents), 14)
        self.assertEqual(len(self.reg.tables), 16)
        self.assertEqual(set(self.reg.transitions), {"candidates", "requisitions", "interviews"})

    def test_capabilities_are_compact(self):
        caps = self.reg.capabilities("agent_5")
        tables = {r["table"] for r in caps["resources"]}
        self.assertEqual(tables, {"candidates", "candidate_details", "screening_results"})
        # discovery must NOT leak column lists - that is describe_resource's job
        for resource in caps["resources"]:
            self.assertNotIn("columns", resource)

    def test_agent_cannot_write_outside_its_grant(self):
        with self.assertRaises(CapabilityError):
            self.reg.authorize_write("agent_5", "offers", "insert", ["salary"])

    def test_agent_cannot_read_outside_its_grant(self):
        with self.assertRaises(CapabilityError):
            self.reg.authorize_read("agent_5", "offer_letters", None)

    def test_column_level_read_enforcement(self):
        with self.assertRaises(SchemaError):
            self.reg.authorize_read("agent_5", "candidates", ["salary"])

    def test_unknown_agent_and_table(self):
        with self.assertRaises(CapabilityError):
            self.reg.agent("agent_99")
        with self.assertRaises(SchemaError):
            self.reg.table("not_a_table")

    def test_only_agent_11_may_cascade(self):
        self.reg.authorize_cascade("agent_11")
        for other in ("agent_9", "agent_10", "agent_1"):
            with self.assertRaises(CapabilityError):
                self.reg.authorize_cascade(other)

    def test_no_agent_holds_delete_by_default(self):
        for agent_id, grant in self.reg.agents.items():
            for table, spec in (grant.get("write") or {}).items():
                self.assertNotIn("delete", spec.get("ops") or [],
                                 f"{agent_id} unexpectedly holds delete on {table}")


class StatusLadderTests(unittest.TestCase):
    def setUp(self):
        self.reg = load_registry()

    def test_insert_may_set_initial_state_only(self):
        # a row has to be born somewhere
        self.reg.authorize_write("agent_4", "candidates", "insert",
                                 ["name", "status"], {"name": "A", "status": "Applied"})
        self.reg.authorize_write("agent_6", "interviews", "insert",
                                 ["candidate_id", "status"],
                                 {"candidate_id": 1, "status": "Scheduled"})
        with self.assertRaises(CapabilityError):
            self.reg.authorize_write("agent_4", "candidates", "insert",
                                     ["name", "status"], {"name": "A", "status": "Hired"})

    def test_status_cannot_be_updated_directly(self):
        with self.assertRaises(CapabilityError):
            self.reg.authorize_write("agent_5", "candidates", "update",
                                     ["status"], {"status": "Interview"})

    def test_illegal_move_reports_legal_targets(self):
        ladder = self.reg.transitions["candidates"]
        with self.assertRaises(TransitionError) as ctx:
            ladder.validate("Applied", "Hired")
        self.assertEqual(ctx.exception.extra["legal_targets"], ["Screening", "Declined"])

    def test_extra_interview_round_is_legal(self):
        self.reg.transitions["candidates"].validate("Interview", "Interview")

    def test_agent_may_only_set_its_own_targets(self):
        self.reg.authorize_transition("agent_5", "candidates", "Interview")
        with self.assertRaises(CapabilityError):
            self.reg.authorize_transition("agent_5", "candidates", "Hired")
        with self.assertRaises(CapabilityError):
            self.reg.authorize_transition("agent_3", "candidates", "Hired")

    def test_every_ladder_is_closed(self):
        for entity, ladder in self.reg.transitions.items():
            states = set(ladder.map)
            self.assertIn(ladder.initial, states, entity)
            for state, targets in ladder.map.items():
                for target in targets:
                    self.assertIn(target, states, f"{entity}: {state} -> {target}")


class FilterTests(unittest.TestCase):
    ROWS = [
        {"id": 1, "score": 80, "status": "Applied", "name": "A. Rao", "rejected_at": None},
        {"id": 2, "score": 55, "status": "Screening", "name": "B. Iyer", "rejected_at": "2026-01-01"},
        {"id": 3, "score": 90, "status": "Applied", "name": "C. Rao", "rejected_at": None},
    ]

    def test_equality_shorthand(self):
        self.assertEqual(len(filt.apply_to_rows(self.ROWS, {"status": "Applied"})), 2)

    def test_comparison_operators(self):
        self.assertEqual([r["id"] for r in filt.apply_to_rows(self.ROWS, {"score": {"gte": 80}})], [1, 3])
        self.assertEqual([r["id"] for r in filt.apply_to_rows(self.ROWS, {"score": {"lt": 60}})], [2])

    def test_in_and_null_and_ilike(self):
        self.assertEqual(len(filt.apply_to_rows(self.ROWS, {"status": {"in": ["Applied", "Screening"]}})), 3)
        self.assertEqual(len(filt.apply_to_rows(self.ROWS, {"rejected_at": {"is_null": True}})), 2)
        self.assertEqual(len(filt.apply_to_rows(self.ROWS, {"name": {"ilike": "rao"}})), 2)

    def test_clauses_are_anded(self):
        rows = filt.apply_to_rows(self.ROWS, {"status": "Applied", "score": {"gte": 85}})
        self.assertEqual([r["id"] for r in rows], [3])

    def test_bad_operator_is_rejected(self):
        with self.assertRaises(SchemaError):
            filt.apply_to_rows(self.ROWS, {"score": {"approximately": 80}})
        with self.assertRaises(SchemaError):
            filt.apply_to_rows(self.ROWS, {"status": {"in": "Applied"}})

    def test_live_and_fallback_paths_agree(self):
        """The whole point of duplicating the operators: a degraded read must
        filter identically to a live one."""
        client = use(FakeClient({"candidates": [dict(r) for r in self.ROWS]}))
        live = db.select("candidates", filters={"score": {"gte": 80}}, limit=10)
        offline = filt.apply_to_rows(self.ROWS, {"score": {"gte": 80}})
        self.assertEqual([r["id"] for r in live["rows"]], [r["id"] for r in offline])
        self.assertEqual(client.calls[0][0], "select")


class FallbackTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        os.environ["JSON_FALLBACK_DIR"] = self.tmp
        os.makedirs(os.path.join(self.tmp, "data"), exist_ok=True)
        with open(os.path.join(self.tmp, "data", "schedule_roster.json"), "w") as fh:
            json.dump([{"id": 1, "task_name": "Tech round", "status": "Available"}], fh)

    def test_transient_failure_is_retried_then_succeeds(self):
        client = use(FlakyClient({"candidates": [{"id": 1, "name": "A"}]}, fail_times=2))
        result = db.select("candidates", limit=5)
        self.assertEqual(result["source"], "database")
        self.assertFalse(result["stale"])

    def test_constraint_violation_is_not_retried(self):
        error = Exception("duplicate key value violates unique constraint")
        client = use(FlakyClient({}, error=error, fail_times=99))
        with self.assertRaises(DatabaseError):
            db.insert("candidates", {"name": "A"})

    def test_read_degrades_to_json_twin_and_is_flagged(self):
        use(FlakyClient({}, fail_times=99))
        result = db.select("schedule_roster", limit=5)
        self.assertEqual(result["source"], "json_fallback")
        self.assertTrue(result["stale"])
        self.assertIn("warning", result)

    def test_empty_table_also_falls_back(self):
        use(FakeClient({"schedule_roster": []}))
        result = db.select("schedule_roster", limit=5)
        self.assertEqual(result["source"], "json_fallback")
        self.assertTrue(result["stale"])

    def test_read_without_a_twin_fails_honestly(self):
        use(FlakyClient({}, fail_times=99))
        with self.assertRaises(DatabaseDownError):
            db.select("candidates")

    def test_writes_never_fall_back(self):
        use(FlakyClient({}, fail_times=99))
        for call in (
            lambda: db.insert("schedule_roster", {"task_name": "x"}),
            lambda: db.update("schedule_roster", {"status": "Busy"}, {"id": 1}),
            lambda: db.upsert("schedule_roster", {"id": 1, "status": "Busy"}),
        ):
            with self.assertRaises(DatabaseDownError) as ctx:
                call()
            self.assertIn("status health", ctx.exception.message)
            self.assertIn("NOT applied", ctx.exception.hint)

    def test_unbounded_update_and_delete_are_refused(self):
        use(FakeClient({"candidates": [{"id": 1}]}))
        with self.assertRaises(SchemaError):
            db.update("candidates", {"name": "x"}, {})
        with self.assertRaises(SchemaError):
            db.delete("candidates", {})

    def test_append_json_appends_rather_than_clobbers(self):
        use(FakeClient({"campus_drives": [{"id": "D1", "candidates": [{"name": "A"}]}]}))
        result = db.append_json("campus_drives", "candidates", {"name": "B"}, {"id": "D1"})
        self.assertEqual(result["length"], 2)

    def test_append_json_refuses_unregistered_column(self):
        use(FakeClient({"campus_drives": [{"id": "D1"}]}))
        with self.assertRaises(SchemaError):
            db.append_json("campus_drives", "college_name", "x", {"id": "D1"})

    def test_append_json_refuses_to_build_on_stale_data(self):
        use(FlakyClient({}, fail_times=99))
        with self.assertRaises(DatabaseDownError):
            db.append_json("campus_drives", "candidates", {"name": "B"}, {"id": "D1"})


def offer_fixture():
    return {
        "offer_links": [{"id": 1, "token": "tok", "offer_letter_id": 7,
                         "candidate_name": "A. Rao", "status": "Pending"}],
        "offer_letters": [{"id": 7, "candidate_id": 42, "status": "Sent"}],
        "offers": [{"id": 3, "candidate_id": 42, "status": "Pending"}],
        "candidates": [{"id": 42, "name": "A. Rao", "status": "Offer"}],
    }


class CascadeTests(unittest.TestCase):
    def test_acceptance_updates_all_four_tables(self):
        client = use(FakeClient(offer_fixture()))
        result = cascade.record_offer_response("tok", "accepted")
        self.assertTrue(result["ok"])
        self.assertEqual(client.data["offer_links"][0]["status"], "Accepted")
        self.assertEqual(client.data["offer_letters"][0]["status"], "Accepted")
        self.assertEqual(client.data["offers"][0]["status"], "Accepted")
        self.assertEqual(client.data["candidates"][0]["status"], "Hired")

    def test_decline_sets_declined_everywhere(self):
        client = use(FakeClient(offer_fixture()))
        cascade.record_offer_response("tok", "declined")
        self.assertEqual(client.data["candidates"][0]["status"], "Declined")
        self.assertEqual(client.data["offer_links"][0]["status"], "Declined")

    def test_already_resolved_link_is_a_noop(self):
        data = offer_fixture()
        data["offer_links"][0]["status"] = "Accepted"
        client = use(FakeClient(data))
        result = cascade.record_offer_response("tok", "declined")
        self.assertTrue(result.get("noop"))
        self.assertEqual(client.data["candidates"][0]["status"], "Offer")

    def test_unknown_token_and_bad_decision(self):
        use(FakeClient(offer_fixture()))
        with self.assertRaises(SchemaError):
            cascade.record_offer_response("nope", "accepted")
        with self.assertRaises(SchemaError):
            cascade.record_offer_response("tok", "maybe")

    def test_failure_rolls_back_and_preserves_the_error_code(self):
        client = use(FailingStepClient(offer_fixture(), fail_table="candidates"))
        with self.assertRaises(McpError) as ctx:
            cascade.record_offer_response("tok", "accepted")
        exc = ctx.exception
        # the real cause survives, so the agent can tell retryable from permanent
        self.assertEqual(exc.code, "database_unavailable")
        self.assertEqual(exc.extra["cascade"], "failed")
        # and the earlier tables were put back
        self.assertEqual(client.data["offer_links"][0]["status"], "Pending")
        self.assertEqual(client.data["offer_letters"][0]["status"], "Sent")
        self.assertEqual(client.data["offers"][0]["status"], "Pending")


class AuthTests(unittest.TestCase):
    def tearDown(self):
        for key in ("REQUIRE_AGENT_AUTH", "AGENT_TOKENS", "AGENT_TOKENS_FILE"):
            os.environ.pop(key, None)

    def test_disabled_by_default(self):
        auth.authenticate("agent_5", None)  # stdio default: no-op

    def test_token_required_when_enabled(self):
        os.environ["REQUIRE_AGENT_AUTH"] = "true"
        os.environ["AGENT_TOKENS"] = json.dumps({"agent_5": "s3cret"})
        auth.authenticate("agent_5", "s3cret")
        with self.assertRaises(McpError):
            auth.authenticate("agent_5", "wrong")
        with self.assertRaises(McpError):
            auth.authenticate("agent_5", None)

    def test_cannot_impersonate_another_agent(self):
        os.environ["REQUIRE_AGENT_AUTH"] = "true"
        os.environ["AGENT_TOKENS"] = json.dumps({"agent_5": "a", "agent_11": "b"})
        with self.assertRaises(McpError):
            auth.authenticate("agent_11", "a")

    def test_error_does_not_reveal_which_agents_exist(self):
        os.environ["REQUIRE_AGENT_AUTH"] = "true"
        os.environ["AGENT_TOKENS"] = json.dumps({"agent_5": "a"})
        try:
            auth.authenticate("agent_5", "wrong")
        except McpError as known:
            first = known.message
        try:
            auth.authenticate("agent_99", "wrong")
        except McpError as unknown:
            second = unknown.message
        self.assertEqual(first, second)

    def test_refuses_unauthenticated_http_on_a_public_interface(self):
        with self.assertRaises(SystemExit):
            auth.assert_safe_startup("http", "0.0.0.0")
        auth.assert_safe_startup("http", "127.0.0.1")   # local dev is allowed
        auth.assert_safe_startup("stdio", "0.0.0.0")    # irrelevant for stdio

    def test_auth_makes_public_binding_allowed(self):
        os.environ["REQUIRE_AGENT_AUTH"] = "true"
        auth.assert_safe_startup("http", "0.0.0.0")


if __name__ == "__main__":
    unittest.main(verbosity=2)
