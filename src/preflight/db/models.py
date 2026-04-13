"""
SQLAlchemy ORM models for Preflight.

Covers the essential tables for Phase 1 persistence:
- User (minimal, Entra ID-backed in production)
- Request (business requests with classification)
- Assessment (append-only assessment versions)
- PersonaFinding (per-persona assessment results)
- AuthorityAction (vetoes, escalations, sign-offs)
- Condition (approval conditions lifecycle)
- AuditLog (NEN 7513 hash-chained append-only log)

Design decisions:
- UUID primary keys everywhere
- JSON for flexible structured data (findings, conditions, documents)
- Append-only assessments (version + parent_id)
- Async session support via sqlalchemy[asyncio]
"""

from __future__ import annotations

import hashlib
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    JSON,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
    Index,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


def _uuid() -> str:
    return str(uuid.uuid4())


def _now() -> datetime:
    return datetime.now(timezone.utc)


# ---------------------------------------------------------------------------
# User
# ---------------------------------------------------------------------------


class User(Base):
    __tablename__ = "user"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    entra_id: Mapped[Optional[str]] = mapped_column(String, unique=True)
    display_name: Mapped[str] = mapped_column(String, nullable=False)
    email: Mapped[str] = mapped_column(String, nullable=False)
    role: Mapped[str] = mapped_column(String, default="requestor")
    department: Mapped[Optional[str]] = mapped_column(String)
    clearance_level: Mapped[str] = mapped_column(String, default="internal")
    clinical_access: Mapped[bool] = mapped_column(Boolean, default=False)
    language: Mapped[str] = mapped_column(String, default="nl")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


# ---------------------------------------------------------------------------
# Request — the business request being assessed
# ---------------------------------------------------------------------------


class Request(Base):
    __tablename__ = "request"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    external_id: Mapped[Optional[str]] = mapped_column(String, unique=True)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    request_type: Mapped[str] = mapped_column(String, nullable=False)
    impact_level: Mapped[str] = mapped_column(String, nullable=False)
    triage_floor_applied: Mapped[Optional[list]] = mapped_column(JSON, default=list)
    state: Mapped[str] = mapped_column(String, default="SUBMITTED")
    submitted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now
    )
    submitted_by: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("user.id")
    )
    attachments: Mapped[Optional[list]] = mapped_column(JSON, default=list)
    adaptive_fields: Mapped[Optional[dict]] = mapped_column(JSON, default=dict)
    landscape_context: Mapped[Optional[dict]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    assessments: Mapped[list["Assessment"]] = relationship(
        back_populates="request", order_by="Assessment.version"
    )


# ---------------------------------------------------------------------------
# Assessment — append-only, versioned
# ---------------------------------------------------------------------------


class Assessment(Base):
    __tablename__ = "assessment"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    external_id: Mapped[Optional[str]] = mapped_column(String, unique=True)
    request_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("request.id"), nullable=False
    )
    version: Mapped[int] = mapped_column(Integer, default=1)
    parent_id: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("assessment.id")
    )

    assessment_mode: Mapped[str] = mapped_column(String, default="fast")
    selected_perspectives: Mapped[Optional[list]] = mapped_column(JSON, default=list)
    triage_treatment: Mapped[str] = mapped_column(String, default="standard-review")
    triage_reason: Mapped[Optional[str]] = mapped_column(Text)

    biv_b: Mapped[int] = mapped_column(SmallInteger, default=2)
    biv_i: Mapped[int] = mapped_column(SmallInteger, default=2)
    biv_v: Mapped[int] = mapped_column(SmallInteger, default=2)
    biv_rpo: Mapped[Optional[str]] = mapped_column(String)
    biv_rto: Mapped[Optional[str]] = mapped_column(String)

    zira_domain: Mapped[Optional[str]] = mapped_column(String)
    zira_positioning: Mapped[Optional[dict]] = mapped_column(JSON, default=dict)

    recommendation: Mapped[str] = mapped_column(String, default="conditional")
    board_time_est: Mapped[Optional[str]] = mapped_column(String)

    persona_version: Mapped[str] = mapped_column(String, default="1.0.0")
    persona_hash: Mapped[str] = mapped_column(String, default="")

    documents: Mapped[Optional[dict]] = mapped_column(JSON, default=dict)
    diagrams: Mapped[Optional[dict]] = mapped_column(JSON, default=dict)
    principetoets: Mapped[Optional[dict]] = mapped_column(JSON, default=dict)
    risk_register: Mapped[Optional[list]] = mapped_column(JSON, default=list)
    citation_appendix: Mapped[Optional[str]] = mapped_column(Text)
    clarification_questions: Mapped[Optional[list]] = mapped_column(JSON, default=list)
    delta_changes: Mapped[Optional[list]] = mapped_column(JSON, default=list)
    reassessed_perspectives: Mapped[Optional[list]] = mapped_column(JSON, default=list)

    status: Mapped[str] = mapped_column(String, default="DRAFT")
    reviewed_by: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("user.id")
    )
    reviewed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    request: Mapped["Request"] = relationship(back_populates="assessments")
    persona_findings: Mapped[list["PersonaFinding"]] = relationship(
        back_populates="assessment"
    )
    authority_actions: Mapped[list["AuthorityAction"]] = relationship(
        back_populates="assessment"
    )
    conditions: Mapped[list["Condition"]] = relationship(back_populates="assessment")

    __table_args__ = (
        UniqueConstraint("request_id", "version"),
        Index("idx_assessment_request", "request_id"),
        Index("idx_assessment_parent", "parent_id"),
    )


# ---------------------------------------------------------------------------
# PersonaFinding — per-persona assessment result
# ---------------------------------------------------------------------------


class PersonaFinding(Base):
    __tablename__ = "persona_finding"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    assessment_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("assessment.id"), nullable=False
    )
    perspective_id: Mapped[str] = mapped_column(String, nullable=False)
    persona_name: Mapped[str] = mapped_column(String, nullable=False)
    persona_role: Mapped[str] = mapped_column(String, nullable=False)
    rating: Mapped[str] = mapped_column(String, nullable=False)
    authority_type: Mapped[Optional[str]] = mapped_column(String)
    authority_triggered: Mapped[bool] = mapped_column(Boolean, default=False)
    findings: Mapped[Optional[list]] = mapped_column(JSON, default=list)
    conditions: Mapped[Optional[list]] = mapped_column(JSON, default=list)
    hidden_concern: Mapped[Optional[str]] = mapped_column(Text)
    strongest_objection: Mapped[Optional[str]] = mapped_column(Text)
    knowledge_bundle_ids: Mapped[Optional[list]] = mapped_column(JSON, default=list)
    landscape_context_applied: Mapped[Optional[dict]] = mapped_column(
        JSON, default=dict
    )
    persona_version: Mapped[Optional[str]] = mapped_column(String)
    board_override: Mapped[bool] = mapped_column(Boolean, default=False)
    override_reason: Mapped[Optional[str]] = mapped_column(Text)
    overridden_by: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("user.id")
    )
    overridden_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    assessment: Mapped["Assessment"] = relationship(back_populates="persona_findings")

    __table_args__ = (
        Index("idx_finding_assessment", "assessment_id"),
        Index("idx_finding_rating", "rating"),
    )


# ---------------------------------------------------------------------------
# AuthorityAction — vetoes, escalations, sign-offs
# ---------------------------------------------------------------------------


class AuthorityAction(Base):
    __tablename__ = "authority_action"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    assessment_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("assessment.id"), nullable=False
    )
    finding_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("persona_finding.id"), nullable=False
    )
    action_type: Mapped[str] = mapped_column(String, nullable=False)
    persona_name: Mapped[str] = mapped_column(String, nullable=False)
    label: Mapped[str] = mapped_column(String, nullable=False)
    requires_sign_off: Mapped[str] = mapped_column(String, nullable=False)
    sign_off_status: Mapped[str] = mapped_column(String, default="PENDING")
    signed_off_by: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("user.id")
    )
    signed_off_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    sign_off_notes: Mapped[Optional[str]] = mapped_column(Text)
    pipeline_halted: Mapped[bool] = mapped_column(Boolean, default=False)
    halt_reason: Mapped[Optional[str]] = mapped_column(Text)
    draft_disclaimer: Mapped[str] = mapped_column(
        Text, default="Authority output is a DRAFT requiring human sign-off"
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    assessment: Mapped["Assessment"] = relationship(back_populates="authority_actions")

    __table_args__ = (
        Index("idx_authority_assessment", "assessment_id"),
        Index("idx_authority_signoff", "sign_off_status"),
    )


# ---------------------------------------------------------------------------
# Condition — approval conditions lifecycle
# ---------------------------------------------------------------------------


class Condition(Base):
    __tablename__ = "condition"

    VALID_STATUSES = ("OPEN", "IN_PROGRESS", "MET", "WAIVED", "OVERDUE")
    VALID_TRANSITIONS = {
        "OPEN": {"IN_PROGRESS", "WAIVED", "OVERDUE"},
        "IN_PROGRESS": {"MET", "WAIVED", "OVERDUE"},
        "OVERDUE": {"IN_PROGRESS", "WAIVED"},
        "MET": set(),
        "WAIVED": set(),
    }

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    external_id: Mapped[Optional[str]] = mapped_column(String, unique=True)
    assessment_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("assessment.id"), nullable=False
    )
    condition_text: Mapped[str] = mapped_column(Text, nullable=False)
    source_persona: Mapped[str] = mapped_column(String, nullable=False)
    source_finding_id: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("persona_finding.id")
    )
    status: Mapped[str] = mapped_column(String, default="OPEN")
    owner: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("user.id"))
    due_date: Mapped[Optional[datetime]] = mapped_column(DateTime)
    evidence: Mapped[Optional[str]] = mapped_column(Text)
    reminders_sent: Mapped[int] = mapped_column(Integer, default=0)
    last_reminder_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True)
    )
    escalation_count: Mapped[int] = mapped_column(Integer, default=0)
    escalation_to: Mapped[Optional[str]] = mapped_column(String)
    resolved_by: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("user.id")
    )
    resolved_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    resolution_notes: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    assessment: Mapped["Assessment"] = relationship(back_populates="conditions")

    def can_transition(self, new_status: str) -> bool:
        if new_status not in self.VALID_STATUSES:
            return False
        allowed = self.VALID_TRANSITIONS.get(self.status, set())
        return new_status in allowed

    __table_args__ = (Index("idx_condition_assessment", "assessment_id"),)


# ---------------------------------------------------------------------------
# AuditLog — NEN 7513 hash-chained append-only
# ---------------------------------------------------------------------------


class AuditLog(Base):
    __tablename__ = "audit_log"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    event_type: Mapped[str] = mapped_column(String, nullable=False)
    action: Mapped[str] = mapped_column(String, nullable=False)
    actor_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("user.id"), nullable=False
    )
    actor_role: Mapped[str] = mapped_column(String, nullable=False)
    resource_type: Mapped[Optional[str]] = mapped_column(String)
    resource_id: Mapped[Optional[str]] = mapped_column(String(36))
    assessment_id: Mapped[Optional[str]] = mapped_column(String(36))
    details: Mapped[Optional[dict]] = mapped_column(JSON)
    classification: Mapped[str] = mapped_column(String, default="internal")
    source_ip: Mapped[Optional[str]] = mapped_column(String)
    user_agent: Mapped[Optional[str]] = mapped_column(String)
    previous_hash: Mapped[str] = mapped_column(String, default="0" * 64)
    entry_hash: Mapped[str] = mapped_column(String, default="0" * 64)

    __table_args__ = (
        Index("idx_audit_type", "event_type", "timestamp"),
        Index("idx_audit_actor", "actor_id", "timestamp"),
        Index("idx_audit_assessment", "assessment_id"),
    )


# ---------------------------------------------------------------------------
# Clarification — pre-assessment clarification questions
# ---------------------------------------------------------------------------


class Clarification(Base):
    __tablename__ = "clarification"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    request_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("request.id"), nullable=False
    )
    persona_name: Mapped[str] = mapped_column(String, nullable=False)
    persona_role: Mapped[str] = mapped_column(String, nullable=False)
    question: Mapped[str] = mapped_column(Text, nullable=False)
    reason: Mapped[Optional[str]] = mapped_column(Text)
    required: Mapped[bool] = mapped_column(Boolean, default=True)

    answered: Mapped[bool] = mapped_column(Boolean, default=False)
    answer: Mapped[Optional[str]] = mapped_column(Text)
    answered_by: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("user.id")
    )
    answered_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    __table_args__ = (Index("idx_clarification_request", "request_id"),)


# ---------------------------------------------------------------------------
# PersonaVersion — persona definition snapshots
# ---------------------------------------------------------------------------


class PersonaVersion(Base):
    __tablename__ = "persona_version"

    version: Mapped[str] = mapped_column(String, primary_key=True)
    date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    persona_count: Mapped[int] = mapped_column(Integer, nullable=False)
    definition_hash: Mapped[str] = mapped_column(String, nullable=False)
    changelog: Mapped[Optional[str]] = mapped_column(Text)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


# ---------------------------------------------------------------------------
# BoardDecision — board recording of decisions
# ---------------------------------------------------------------------------


class BoardDecision(Base):
    __tablename__ = "board_decision"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    assessment_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("assessment.id"), nullable=False
    )
    decision: Mapped[str] = mapped_column(String, nullable=False)
    decided_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    decided_by: Mapped[str] = mapped_column(
        String(36), ForeignKey("user.id"), nullable=False
    )
    items: Mapped[Optional[list]] = mapped_column(JSON, default=list)
    board_time_actual: Mapped[Optional[str]] = mapped_column(String)
    notes: Mapped[Optional[str]] = mapped_column(Text)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    overrides: Mapped[list["BoardOverride"]] = relationship(back_populates="decision")

    __table_args__ = (Index("idx_decision_assessment", "assessment_id"),)


# ---------------------------------------------------------------------------
# BoardOverride — board overrides of persona findings
# ---------------------------------------------------------------------------


class BoardOverride(Base):
    __tablename__ = "board_override"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    decision_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("board_decision.id"), nullable=False
    )
    finding_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("persona_finding.id"), nullable=False
    )
    original_rating: Mapped[str] = mapped_column(String, nullable=False)
    override_decision: Mapped[str] = mapped_column(String, nullable=False)
    override_reason: Mapped[str] = mapped_column(String, nullable=False)
    overridden_by: Mapped[str] = mapped_column(
        String(36), ForeignKey("user.id"), nullable=False
    )
    overridden_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now
    )
    retrospective_validated: Mapped[Optional[bool]] = mapped_column(Boolean)
    retrospective_notes: Mapped[Optional[str]] = mapped_column(Text)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    decision: Mapped["BoardDecision"] = relationship(back_populates="overrides")

    __table_args__ = (Index("idx_override_finding", "finding_id"),)


# ---------------------------------------------------------------------------
# Retrospective — did the risk materialize?
# ---------------------------------------------------------------------------


class Retrospective(Base):
    __tablename__ = "retrospective"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    assessment_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("assessment.id"), nullable=False
    )
    scheduled_date: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    completed_date: Mapped[Optional[datetime]] = mapped_column(DateTime)
    completed_by: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("user.id")
    )
    finding_outcomes: Mapped[Optional[list]] = mapped_column(JSON, default=list)
    condition_outcomes: Mapped[Optional[list]] = mapped_column(JSON, default=list)
    accuracy_score: Mapped[Optional[float]] = mapped_column(Float)
    unpredicted_events: Mapped[Optional[list]] = mapped_column(JSON, default=list)
    calibration_recommendations: Mapped[Optional[list]] = mapped_column(
        JSON, default=list
    )
    status: Mapped[str] = mapped_column(String, default="SCHEDULED")

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    __table_args__ = (Index("idx_retrospective_assessment", "assessment_id"),)


# ---------------------------------------------------------------------------
# PersonaCalibration — persona accuracy tracking
# ---------------------------------------------------------------------------


class PersonaCalibration(Base):
    __tablename__ = "persona_calibration"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    persona_name: Mapped[str] = mapped_column(String, nullable=False)
    perspective_id: Mapped[str] = mapped_column(String, nullable=False)
    period_start: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    period_end: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    total_assessments: Mapped[int] = mapped_column(Integer, default=0)
    approve_count: Mapped[int] = mapped_column(Integer, default=0)
    conditional_count: Mapped[int] = mapped_column(Integer, default=0)
    concern_count: Mapped[int] = mapped_column(Integer, default=0)
    block_count: Mapped[int] = mapped_column(Integer, default=0)
    override_count: Mapped[int] = mapped_column(Integer, default=0)
    override_rate: Mapped[Optional[float]] = mapped_column(Float)
    override_decisions: Mapped[Optional[list]] = mapped_column(JSON, default=list)
    predictions_correct: Mapped[int] = mapped_column(Integer, default=0)
    predictions_wrong: Mapped[int] = mapped_column(Integer, default=0)
    retrospective_accuracy: Mapped[Optional[float]] = mapped_column(Float)
    alignment_score: Mapped[Optional[float]] = mapped_column(Float)
    recommendation: Mapped[Optional[str]] = mapped_column(Text)
    recommended_change: Mapped[Optional[str]] = mapped_column(Text)
    assessment_ids: Mapped[Optional[list]] = mapped_column(JSON, default=list)
    retrospective_ids: Mapped[Optional[list]] = mapped_column(JSON, default=list)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    __table_args__ = (
        UniqueConstraint(
            "persona_name", "perspective_id", "period_start", "period_end"
        ),
    )


# ---------------------------------------------------------------------------
# KnowledgeSource — regulatory/policy documents for RAG
# ---------------------------------------------------------------------------


class KnowledgeSource(Base):
    __tablename__ = "knowledge_source"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    source_id: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    title: Mapped[str] = mapped_column(String, nullable=False)
    source_type: Mapped[str] = mapped_column(String, nullable=False)
    language: Mapped[str] = mapped_column(String, default="nl")
    content: Mapped[str] = mapped_column(Text, nullable=False)
    chunk_text: Mapped[str] = mapped_column(Text, nullable=False)
    source_file: Mapped[Optional[str]] = mapped_column(String)
    page_number: Mapped[Optional[int]] = mapped_column(Integer)
    section: Mapped[Optional[str]] = mapped_column(String)
    effective_date: Mapped[Optional[datetime]] = mapped_column(DateTime)
    persona_relevance: Mapped[Optional[list]] = mapped_column(JSON, default=list)
    classification: Mapped[str] = mapped_column(String, default="internal")
    verified: Mapped[bool] = mapped_column(Boolean, default=False)
    verified_by: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("user.id")
    )
    verified_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    citation_count: Mapped[int] = mapped_column(Integer, default=0)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    __table_args__ = (Index("idx_knowledge_type", "source_type"),)


# ---------------------------------------------------------------------------
# KnowledgeChunk — vector-store chunks for RAG retrieval
#
# Note: Vector columns (dense_vector, title_vector, sparse_vector, content_ts)
# are managed directly by PgvectorStore via raw SQL, not through this ORM model.
# The ORM model covers scalar columns for querying and updates via SQLAlchemy.
# ---------------------------------------------------------------------------


class KnowledgeChunkModel(Base):
    __tablename__ = "knowledge_chunk"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    source_id: Mapped[str] = mapped_column(String, nullable=False)
    source_type: Mapped[str] = mapped_column(String, nullable=False)
    title: Mapped[str] = mapped_column(String, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    chunk_text: Mapped[str] = mapped_column(Text, nullable=False)
    context_prefix: Mapped[Optional[str]] = mapped_column(Text)
    enriched_keyword: Mapped[str] = mapped_column(Text, insert_default="")
    enriched_semantic: Mapped[str] = mapped_column(Text, insert_default="")
    language: Mapped[str] = mapped_column(String, insert_default="nl")
    content_type: Mapped[str] = mapped_column(String, insert_default="generic")
    classification: Mapped[str] = mapped_column(
        String, default="internal", server_default="internal"
    )
    metadata_: Mapped[Optional[dict]] = mapped_column("metadata", JSON, default=dict)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    __table_args__ = (
        Index("idx_chunk_source", "source_id"),
        Index("idx_chunk_type", "content_type"),
    )


# ---------------------------------------------------------------------------
# Citation — post-generation citation tracking
# ---------------------------------------------------------------------------


class Citation(Base):
    __tablename__ = "citation"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    assessment_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("assessment.id"), nullable=False
    )
    finding_id: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("persona_finding.id")
    )
    source_type: Mapped[str] = mapped_column(String, nullable=False)
    source_id: Mapped[str] = mapped_column(String, nullable=False)
    excerpt: Mapped[Optional[str]] = mapped_column(Text)
    verified: Mapped[Optional[bool]] = mapped_column(Boolean)
    verification_failure: Mapped[Optional[str]] = mapped_column(Text)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    __table_args__ = (
        Index("idx_citation_assessment", "assessment_id"),
        Index("idx_citation_source", "source_type", "source_id"),
    )


# ---------------------------------------------------------------------------
# Vendor — cumulative vendor intelligence
# ---------------------------------------------------------------------------


class Vendor(Base):
    __tablename__ = "vendor"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    name: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    assessments_count: Mapped[int] = mapped_column(Integer, default=0)
    approval_rate: Mapped[Optional[float]] = mapped_column(Float)
    open_conditions: Mapped[int] = mapped_column(Integer, default=0)
    nen7510_status: Mapped[Optional[str]] = mapped_column(String)
    nen7512_status: Mapped[Optional[str]] = mapped_column(String)
    nen7513_status: Mapped[Optional[str]] = mapped_column(String)
    aivg_status: Mapped[Optional[str]] = mapped_column(String)
    dpa_in_place: Mapped[bool] = mapped_column(Boolean, default=False)
    dpia_required: Mapped[Optional[bool]] = mapped_column(Boolean)
    sbom_available: Mapped[bool] = mapped_column(Boolean, default=False)
    sbom_format: Mapped[Optional[str]] = mapped_column(String)
    systems_count: Mapped[int] = mapped_column(Integer, default=0)
    notes: Mapped[Optional[str]] = mapped_column(Text)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


# ---------------------------------------------------------------------------
# System — ArchiMate-aligned system records
# ---------------------------------------------------------------------------


class System(Base):
    __tablename__ = "system"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    archimate_id: Mapped[Optional[str]] = mapped_column(String, unique=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    type: Mapped[str] = mapped_column(String, nullable=False)
    layer: Mapped[str] = mapped_column(String, nullable=False)
    lifecycle_status: Mapped[str] = mapped_column(String, default="production")
    vendor_id: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("vendor.id")
    )
    biv_b: Mapped[Optional[int]] = mapped_column(SmallInteger)
    biv_i: Mapped[Optional[int]] = mapped_column(SmallInteger)
    biv_v: Mapped[Optional[int]] = mapped_column(SmallInteger)
    dr_tier: Mapped[Optional[int]] = mapped_column(SmallInteger)
    properties: Mapped[Optional[dict]] = mapped_column(JSON, default=dict)
    debt_items: Mapped[Optional[list]] = mapped_column(JSON, default=list)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    relationships_as_source: Mapped[list["SystemRelationship"]] = relationship(
        back_populates="source", foreign_keys="SystemRelationship.source_id"
    )
    relationships_as_target: Mapped[list["SystemRelationship"]] = relationship(
        back_populates="target", foreign_keys="SystemRelationship.target_id"
    )
    debt: Mapped[list["ArchitectureDebt"]] = relationship(back_populates="system")

    __table_args__ = (
        Index("idx_system_archimate", "archimate_id"),
        Index("idx_system_lifecycle", "lifecycle_status"),
    )


# ---------------------------------------------------------------------------
# SystemRelationship — ArchiMate relationship graph edges
# ---------------------------------------------------------------------------


class SystemRelationship(Base):
    __tablename__ = "system_relationship"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    source_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("system.id"), nullable=False
    )
    target_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("system.id"), nullable=False
    )
    relationship_type: Mapped[str] = mapped_column(String, nullable=False)
    source_model: Mapped[str] = mapped_column(String, default="hospital")
    cascade_weight: Mapped[float] = mapped_column(Float, default=1.0)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    source: Mapped["System"] = relationship(
        back_populates="relationships_as_source", foreign_keys=[source_id]
    )
    target: Mapped["System"] = relationship(
        back_populates="relationships_as_target", foreign_keys=[target_id]
    )

    __table_args__ = (
        UniqueConstraint("source_id", "target_id", "relationship_type", "source_model"),
        Index("idx_rel_source", "source_id"),
        Index("idx_rel_target", "target_id"),
    )


# ---------------------------------------------------------------------------
# ArchitectureDebt — technical/integration/security debt tracking
# ---------------------------------------------------------------------------


class ArchitectureDebt(Base):
    __tablename__ = "architecture_debt"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    system_id: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("system.id")
    )
    archimate_element_id: Mapped[Optional[str]] = mapped_column(String)
    debt_type: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    severity: Mapped[str] = mapped_column(String, default="medium")
    status: Mapped[str] = mapped_column(String, default="open")
    resolves_via: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("assessment.id")
    )
    detected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    resolved_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    system: Mapped[Optional["System"]] = relationship(back_populates="debt")

    __table_args__ = (Index("idx_debt_system", "system_id"),)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def compute_audit_hash(entry: AuditLog, previous_hash: str) -> str:
    payload = f"{entry.timestamp.isoformat()}|{entry.event_type}|{entry.action}|{entry.actor_id}|{previous_hash}"
    return hashlib.sha256(payload.encode()).hexdigest()
