"""Abstract interfaces every MCP client (real or mock) implements.
Swap a mock for a real MCP-backed client without touching agent.py."""
from __future__ import annotations
from abc import ABC, abstractmethod


class DatabaseMCP(ABC):
    @abstractmethod
    def read(self, table: str, filters: dict) -> list[dict]: ...
    @abstractmethod
    def write(self, table: str, op: str, filters: dict, payload: dict, idempotency_key: str) -> dict: ...


class AnalyticsMCP(ABC):
    @abstractmethod
    def compute_hr_score(self, ratings: dict, is_leadership_track: bool) -> int | None:
        """Return None to signal degraded/unavailable -> caller falls back to scoring.py."""


class PolicyMCP(ABC):
    @abstractmethod
    def check(self, job_id: int, cohort: list[int], decisions: dict) -> dict:
        """Returns {"allowed": bool, "violations": [...], "approval_required_by": str|None}"""


class SalaryBandMCP(ABC):
    @abstractmethod
    def check(self, grade: str, estimated_ctc: float, candidate_expectation: float | None) -> dict: ...


class ResumeMCP(ABC):
    @abstractmethod
    def get_profile(self, candidate_id: int) -> dict: ...


class DocumentMCP(ABC):
    @abstractmethod
    def generate(self, template: str, candidate: dict, job: dict, round_type: str) -> str | None: ...


class NotificationMCP(ABC):
    @abstractmethod
    def send(self, channel: str, recipient: str, template_id: str, variables: dict) -> dict: ...


class MeetMCP(ABC):
    @abstractmethod
    def validate(self, meet_link: str) -> dict: ...


class LLMRationaleMCP(ABC):
    @abstractmethod
    def draft_rationale(self, evidence: dict) -> str:
        """MUST NEVER be asked for or return a numeric score. Text only."""
