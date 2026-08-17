"""Strict contracts exchanged by the KHALINOS agent team."""

from __future__ import annotations

import hashlib
import json
import re
from datetime import UTC, datetime
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, Field, model_validator


def utc_now() -> str:
    return datetime.now(UTC).isoformat()


def canonical_sha256(value: BaseModel | dict | list) -> str:
    if isinstance(value, BaseModel):
        value = value.model_dump(mode="json", exclude_none=True)
    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


class RunStatus(StrEnum):
    QUEUED = "queued"
    PLANNING = "planning"
    EXECUTING = "executing"
    VERIFYING = "verifying"
    REPAIRING = "repairing"
    PASSED = "passed"
    BLOCKED = "blocked"
    FAILED = "failed"


class UserBrief(BaseModel):
    project_name: str = Field(min_length=2, max_length=80)
    goal: str = Field(min_length=30, max_length=5000)
    constraints: list[str] = Field(default_factory=list, max_length=12)
    acceptance_criteria: list[str] = Field(min_length=2, max_length=10)
    max_quests: int = Field(default=4, ge=2, le=5)
    max_repairs_per_quest: int = Field(default=2, ge=0, le=2)
    authorized_output_files: list[str] = Field(
        default_factory=lambda: [
            "index.html", "styles.css", "app.js", "journey.json", "README.md"
        ],
        min_length=5,
        max_length=5,
    )

    @model_validator(mode="after")
    def fixed_safe_surface(self) -> "UserBrief":
        expected = {"index.html", "styles.css", "app.js", "journey.json", "README.md"}
        if set(self.authorized_output_files) != expected:
            raise ValueError("the autonomous micro-app profile has one fixed output surface")
        return self


class QuestSpec(BaseModel):
    quest_id: str = Field(pattern=r"^Q[1-5]$")
    objective: str = Field(min_length=20, max_length=500)
    acceptance_criteria: list[str] = Field(min_length=1, max_length=8)
    evidence_required: list[str] = Field(min_length=1, max_length=8)
    depends_on: list[str] = Field(default_factory=list, max_length=1)


class QuestPlan(BaseModel):
    product_summary: str = Field(min_length=30, max_length=800)
    architecture_decision: str = Field(min_length=30, max_length=800)
    quests: list[QuestSpec] = Field(min_length=2, max_length=5)

    @model_validator(mode="after")
    def linear_chain(self) -> "QuestPlan":
        expected = [f"Q{index}" for index in range(1, len(self.quests) + 1)]
        if [quest.quest_id for quest in self.quests] != expected:
            raise ValueError("quests must be a contiguous Q1..Qn sequence")
        for index, quest in enumerate(self.quests):
            required = [] if index == 0 else [expected[index - 1]]
            if quest.depends_on != required:
                raise ValueError("quests must form one receipt-gated linear chain")
        return self


class ArtifactFile(BaseModel):
    path: str = Field(pattern=r"^(index\.html|styles\.css|app\.js|journey\.json|README\.md)$")
    content: str = Field(min_length=1, max_length=50_000)


class ArtifactBundle(BaseModel):
    revision_summary: str = Field(min_length=10, max_length=500)
    files: list[ArtifactFile] = Field(min_length=5, max_length=5)

    @model_validator(mode="after")
    def exact_file_set(self) -> "ArtifactBundle":
        paths = [item.path for item in self.files]
        if len(paths) != len(set(paths)):
            raise ValueError("artifact paths must be unique")
        expected = {"index.html", "styles.css", "app.js", "journey.json", "README.md"}
        if set(paths) != expected:
            raise ValueError("artifact bundle must contain the complete authorized file set")
        return self

    def file_map(self) -> dict[str, str]:
        return {item.path: item.content for item in self.files}


class CriterionFinding(BaseModel):
    criterion: str = Field(min_length=3, max_length=500)
    passed: bool
    evidence: str = Field(min_length=3, max_length=1000)


class AgentVerification(BaseModel):
    findings: list[CriterionFinding] = Field(min_length=1, max_length=10)
    verdict: Literal["PASS", "REPAIR"]
    repair_instructions: list[str] = Field(default_factory=list, max_length=8)

    @model_validator(mode="after")
    def consistent_verdict(self) -> "AgentVerification":
        all_pass = all(item.passed for item in self.findings)
        if (self.verdict == "PASS") != all_pass:
            raise ValueError("verdict must match criterion findings")
        if self.verdict == "REPAIR" and not self.repair_instructions:
            raise ValueError("a repair verdict requires bounded repair instructions")
        return self


class DeterministicEvidence(BaseModel):
    passed: bool
    checks: dict[str, bool]
    issues: list[str]
    screenshot_names: list[str] = Field(default_factory=list)


class QuestReceipt(BaseModel):
    receipt_id: str
    quest_id: str
    quest_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    parent_receipt_id: str | None = None
    artifact_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    deterministic_evidence: DeterministicEvidence
    independent_verification: AgentVerification
    repair_rounds: int = Field(ge=0, le=2)
    state: Literal["passed", "blocked"]
    created_at: str = Field(default_factory=utc_now)


class RunRecord(BaseModel):
    run_id: str
    status: RunStatus
    brief_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    current_quest_id: str | None = None
    completed_receipt_ids: list[str] = Field(default_factory=list)
    message: str
    model: str = "gemini-3.5-flash"
    framework: str = "Google ADK 2.6.2"
    cloud_services: list[str] = Field(
        default_factory=lambda: ["Vertex AI", "Cloud Run", "Cloud Storage", "Firestore"]
    )
    model_calls: int = 0
    created_at: str = Field(default_factory=utc_now)
    updated_at: str = Field(default_factory=utc_now)


SAFE_RUN_ID = re.compile(r"^[a-f0-9]{32}$")

