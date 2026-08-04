"""In-memory mock implementations of every MCP except the LLM one.
Replace with real MCP-backed clients later; agent.py only depends on
the abstract interfaces in base.py, not these classes directly."""
from __future__ import annotations
import time
from .base import (
    DatabaseMCP, AnalyticsMCP, PolicyMCP, SalaryBandMCP,
    ResumeMCP, DocumentMCP, NotificationMCP, MeetMCP,
)


class MockDatabaseMCP(DatabaseMCP):
    def __init__(self):
        self.tables: dict[str, list[dict]] = {
            "candidates": [], "candidate_details": [], "interviews": [],
            "interview_scores": [], "jobs": [], "requisitions": [], "screening_results": [],
            "turn2_snapshots": [],
        }
        self._seen_idempotency_keys: set[str] = set()

    def seed(self, table: str, rows: list[dict]) -> None:
        self.tables[table] = rows

    def read(self, table: str, filters: dict) -> list[dict]:
        rows = self.tables.get(table, [])
        return [r for r in rows if all(r.get(k) == v for k, v in filters.items())]

    def write(self, table: str, op: str, filters: dict, payload: dict, idempotency_key: str) -> dict:
        self.tables.setdefault(table, [])
        if idempotency_key in self._seen_idempotency_keys and op == "INSERT":
            # Idempotent replay - do not double-insert. Match on the row's own
            # idempotency_key first (reliable even when filters is {}); fall
            # back to filters for callers that don't store the key on the row.
            existing = [r for r in self.tables[table] if r.get("idempotency_key") == idempotency_key]
            if not existing and filters:
                existing = self.read(table, filters)
            return existing[0] if existing else {}
        self._seen_idempotency_keys.add(idempotency_key)

        if op == "INSERT":
            row = dict(payload)
            row["id"] = len(self.tables[table]) + 1
            self.tables[table].append(row)
            return row
        elif op == "UPDATE":
            updated = None
            for row in self.tables[table]:
                if all(row.get(k) == v for k, v in filters.items()):
                    row.update(payload)
                    updated = row
            return updated or {}
        raise ValueError(f"unsupported op {op}")


class MockAnalyticsMCP(AnalyticsMCP):
    """Simulates the real Analytics MCP. In this mock it deliberately returns
    None (degraded) so the workflow exercises the scoring.py fallback path -
    exactly the path that must never silently be an LLM guess."""
    def __init__(self, always_degraded: bool = True):
        self.always_degraded = always_degraded

    def compute_hr_score(self, ratings: dict, is_leadership_track: bool) -> int | None:
        if self.always_degraded:
            return None
        # even the "working" branch here is still deterministic code,
        # never an LLM call - see scoring.py for the real formula.
        from .. import scoring
        return scoring.compute_hr_score(
            ratings["communication_rating"], ratings["culture_fit_rating"],
            ratings["behaviour_rating"], ratings.get("motivation_rating"),
            ratings.get("leadership_rating"), is_leadership_track,
        )


class MockPolicyMCP(PolicyMCP):
    def __init__(self, allowed: bool = True):
        self.allowed = allowed

    def check(self, job_id: int, cohort: list[int], decisions: dict) -> dict:
        return {"allowed": self.allowed, "violations": [], "approval_required_by": None}


class MockSalaryBandMCP(SalaryBandMCP):
    def check(self, grade: str, estimated_ctc: float, candidate_expectation: float | None) -> dict:
        return {"within_band": True, "band_min": estimated_ctc * 0.85, "band_max": estimated_ctc * 1.15}


class MockResumeMCP(ResumeMCP):
    def get_profile(self, candidate_id: int) -> dict:
        return {"resume_url": f"https://example.com/resumes/{candidate_id}.pdf", "parsed_summary": ""}


class MockDocumentMCP(DocumentMCP):
    def generate(self, template: str, candidate: dict, job: dict, round_type: str) -> str | None:
        return f"https://example.com/docs/{template}-{candidate.get('id')}.pdf"


class MockNotificationMCP(NotificationMCP):
    def send(self, channel: str, recipient: str, template_id: str, variables: dict) -> dict:
        return {"status": "ok", "provider_msg_id": f"msg-{int(time.time())}"}


class MockMeetMCP(MeetMCP):
    def validate(self, meet_link: str) -> dict:
        return {"valid": True, "participants": ["candidate", "interviewer"]}
