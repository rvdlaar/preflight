"""
Preflight FastAPI application — REST API for the assessment pipeline.

All endpoints require authentication except /health.
AuthN: Entra ID OIDC (production) or API key (dev mode).
AuthZ: RBAC role checks + ABAC content-driven access control.
Audit: NEN 7513 compliant logging for every access.

Endpoints:
  POST /assess          — Submit a business request (architect+)
  GET  /assessments     — List assessments (architect+)
  GET  /assessments/{id} — Get assessment details (authz-checked)
  GET  /assessments/{id}/documents/{name} — Get a specific document
  GET  /health          — Health check (no auth required)
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

from fastapi import FastAPI, HTTPException, Depends, BackgroundTasks, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from preflight.db.session import init_db, get_async_session_factory
from preflight.db.models import (
    Request as RequestModel,
    Assessment as AssessmentModel,
    Condition as ConditionModel,
    AuthorityAction,
    PersonaFinding as PersonaFindingModel,
    BoardDecision as BoardDecisionModel,
    BoardOverride as BoardOverrideModel,
)
from preflight.pipeline.orchestrator import run_full_pipeline, PipelineResult
from preflight.llm.client import LLMRouter
from preflight.auth.middleware import (
    configure_auth,
    require_action,
    check_assessment_access,
    _audit_logger,
)
from preflight.auth.authn import AuthUser
from preflight.auth.authz import Action, classify_assessment
from preflight.auth.audit import (
    AuditEntry,
    AuditAction,
    MemoryAuditLogger,
)


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------


class AssessRequest(BaseModel):
    description: str = Field(
        ..., min_length=10, max_length=5000, description="Business request text"
    )
    mode: str = Field(default="fast", pattern=r"^(fast|deep)$")
    model: str = Field(default="llama3.1:8b")
    ollama_url: str = Field(default="http://localhost:11434")
    heuristic_classify: bool = Field(
        default=False, description="Use heuristic instead of LLM for classification"
    )
    archimate_file: Optional[str] = Field(
        default=None, description="Path to .archimate XML file"
    )
    zira: Optional[dict] = Field(default=None)


class AssessmentResponse(BaseModel):
    id: str
    request_id: str
    request_type: str
    impact_level: str
    triage_treatment: str
    recommendation: str
    biv: dict
    documents: list[str]
    diagrams: list[str]
    status: str


class AssessmentDetailResponse(BaseModel):
    id: str
    request_id: str
    request_type: str
    impact_level: str
    classification: Optional[dict] = None
    triage: dict = {}
    biv: dict = {}
    biv_controls: dict = {}
    recommendation: str = ""
    persona_findings: list[dict] = []
    authority_actions: list[dict] = []
    conditions: list[dict] = []
    principetoets: list[dict] = []
    documents: dict[str, str] = {}
    diagrams: dict[str, dict] = {}
    risk_register: Any = None
    citation_appendix: str = ""
    lifecycle: list[dict] = []
    errors: list[str] = []


class HealthResponse(BaseModel):
    status: str
    version: str
    database: str


class ConditionTransitionRequest(BaseModel):
    status: str = Field(..., description="New status: IN_PROGRESS, MET, WAIVED")
    owner: Optional[str] = Field(default=None, description="User ID to assign as owner")
    evidence: Optional[str] = Field(
        default=None, description="Evidence for meeting the condition"
    )
    resolution_notes: Optional[str] = Field(
        default=None, description="Notes on the transition"
    )


class ConditionResponse(BaseModel):
    id: str
    assessment_id: str
    condition_text: str
    source_persona: str
    status: str
    owner: Optional[str] = None
    due_date: Optional[str] = None
    evidence: Optional[str] = None
    escalation_count: int = 0
    resolved_by: Optional[str] = None
    resolved_at: Optional[str] = None
    resolution_notes: Optional[str] = None
    created_at: str = ""
    updated_at: str = ""


# ---------------------------------------------------------------------------
# App setup
# ---------------------------------------------------------------------------

app = FastAPI(
    title="Preflight",
    description="EA intake and pre-assessment API for Dutch hospitals",
    version="0.2.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def startup():
    await init_db()
    configure_auth()


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@app.get("/health", response_model=HealthResponse)
async def health():
    return HealthResponse(
        status="ok",
        version="0.1.0",
        database="connected",
    )


@app.post("/assess", response_model=AssessmentResponse)
async def assess(
    req: AssessRequest,
    background_tasks: BackgroundTasks,
    user: AuthUser = Depends(require_action(Action.RUN_ASSESSMENT)),
):
    router = LLMRouter.from_ollama(req.model, req.ollama_url)

    landscape_context = None
    if req.archimate_file:
        from preflight.archimate import parse_archimate, build_landscape_context

        try:
            model = parse_archimate(req.archimate_file)
            keywords = req.description.lower().split()[:10]
            landscape_context = build_landscape_context(model, keywords)
        except Exception as e:
            raise HTTPException(
                status_code=400, detail=f"Failed to parse ArchiMate file: {e}"
            )

    result = await run_full_pipeline(
        request=req.description,
        client=router,
        landscape_context=landscape_context,
        zira=req.zira,
        mode=req.mode,
        prefer_heuristic_classify=req.heuristic_classify,
    )

    session_factory = get_async_session_factory()
    async with session_factory() as session:
        request_model = RequestModel(
            description=req.description,
            request_type=result.classification.request_type
            if result.classification
            else "new-application",
            impact_level=result.classification.impact_level
            if result.classification
            else "medium",
            state="ASSESSED",
            landscape_context=landscape_context,
        )
        session.add(request_model)
        await session.flush()

        assessment_model = AssessmentModel(
            request_id=request_model.id,
            assessment_mode=req.mode,
            triage_treatment=result.triage.get("treatment", "standard-review"),
            triage_reason=result.triage.get("reason"),
            biv_b=result.biv.get("B", 2),
            biv_i=result.biv.get("I", 2),
            biv_v=result.biv.get("V", 2),
            recommendation=_derive_recommendation(result),
            selected_perspectives=result.perspectives,
            documents=result.documents,
            diagrams=result.diagrams,
            principetoets=result.principetoets
            if isinstance(result.principetoets, dict)
            else {"items": result.principetoets},
            risk_register=result.risk_register
            if isinstance(result.risk_register, list)
            else [],
            citation_appendix=result.citation_appendix,
            persona_version=result.persona_version,
            persona_hash=result.persona_hash,
            status="DRAFT",
        )
        session.add(assessment_model)
        await session.flush()

        if result.persona_findings:
            for pf in result.persona_findings:
                finding_model = PersonaFindingModel(
                    assessment_id=assessment_model.id,
                    perspective_id=pf.get("perspective_id", ""),
                    name=pf.get("name", ""),
                    role=pf.get("role", ""),
                    rating=pf.get("rating", "na"),
                    findings=pf.get("findings", []),
                    conditions=pf.get("conditions", []),
                    authority=pf.get("authority"),
                    strongest_objection=pf.get("strongest_objection", ""),
                    hidden_concern=pf.get("hidden_concern", ""),
                    interaction_round=pf.get("interaction_round", 1),
                    persona_version=pf.get("persona_version", result.persona_version),
                )
                session.add(finding_model)

        if result.authority_actions:
            for action in result.authority_actions:
                action_model = AuthorityAction(
                    assessment_id=assessment_model.id,
                    action_type=action.get("type", ""),
                    persona=action.get("persona", ""),
                    label=action.get("label", ""),
                    triggered=action.get("triggered", False),
                    requires_sign_off=action.get("requires_sign_off", False),
                    draft_disclaimer=action.get("draft_disclaimer", ""),
                    findings=action.get("findings", []),
                    conditions=action.get("conditions", []),
                )
                session.add(action_model)

        if result.conditions:
            for cond in result.conditions:
                cond_model = ConditionModel(
                    assessment_id=assessment_model.id,
                    condition_text=cond.get(
                        "condition_text", cond.get("condition", "")
                    ),
                    source_persona=cond.get("source_persona", ""),
                    source_perspective_id=cond.get("source_perspective_id", ""),
                    status="OPEN",
                )
                session.add(cond_model)

        await session.commit()
        await session.refresh(assessment_model)
        assessment_id = assessment_model.id
        request_id = request_model.id

    return AssessmentResponse(
        id=assessment_id,
        request_id=request_id,
        request_type=result.classification.request_type
        if result.classification
        else "unknown",
        impact_level=result.classification.impact_level
        if result.classification
        else "unknown",
        triage_treatment=result.triage.get("treatment", "unknown"),
        recommendation=_derive_recommendation(result),
        biv=result.biv,
        documents=list(result.documents.keys()),
        diagrams=list(result.diagrams.keys()),
        status="DRAFT",
    )


@app.get("/assessments", response_model=list[AssessmentResponse])
async def list_assessments(
    limit: int = 50,
    offset: int = 0,
    user: AuthUser = Depends(require_action(Action.VIEW_ALL_ASSESSMENTS)),
):
    session_factory = get_async_session_factory()
    async with session_factory() as session:
        from sqlalchemy import select

        stmt = (
            select(AssessmentModel)
            .order_by(AssessmentModel.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        result = await session.execute(stmt)
        assessments = result.scalars().all()

        return [
            AssessmentResponse(
                id=a.id,
                request_id=a.request_id,
                request_type="",
                impact_level="",
                triage_treatment=a.triage_treatment,
                recommendation=a.recommendation,
                biv={"B": a.biv_b, "I": a.biv_i, "V": a.biv_v},
                documents=list(a.documents.keys()) if a.documents else [],
                diagrams=list(a.diagrams.keys()) if a.diagrams else [],
                status=a.status,
            )
            for a in assessments
        ]


@app.get("/assessments/{assessment_id}", response_model=AssessmentDetailResponse)
async def get_assessment(
    assessment_id: str,
    user: AuthUser = Depends(require_action(Action.VIEW_ASSESSMENT)),
):
    session_factory = get_async_session_factory()
    async with session_factory() as session:
        from sqlalchemy import select

        stmt = select(AssessmentModel).where(AssessmentModel.id == assessment_id)
        result = await session.execute(stmt)
        assessment = result.scalar_one_or_none()

        if not assessment:
            raise HTTPException(status_code=404, detail="Assessment not found")

        classification = classify_assessment(
            persona_findings=getattr(assessment, "persona_findings", []) or [],
            authority_actions=getattr(assessment, "authority_actions", []) or [],
        )

        allowed = await check_assessment_access(
            user,
            assessment_id,
            classification,
            AuditAction.ACCESSED,
            source_ip="",
        )
        if not allowed:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied: insufficient clearance for this assessment's classification",
            )

        request_stmt = select(RequestModel).where(
            RequestModel.id == assessment.request_id
        )
        req_result = await session.execute(request_stmt)
        request = req_result.scalar_one_or_none()

        return AssessmentDetailResponse(
            id=assessment.id,
            request_id=assessment.request_id,
            request_type=request.request_type if request else "unknown",
            impact_level=request.impact_level if request else "unknown",
            triage={
                "treatment": assessment.triage_treatment,
                "reason": assessment.triage_reason or "",
            },
            biv={"B": assessment.biv_b, "I": assessment.biv_i, "V": assessment.biv_v},
            recommendation=assessment.recommendation,
            documents=assessment.documents or {},
            diagrams=assessment.diagrams or {},
            principetoets=assessment.principetoets.get("items", [])
            if assessment.principetoets
            else [],
            risk_register=assessment.risk_register,
            citation_appendix=assessment.citation_appendix or "",
            lifecycle=[
                {
                    "state": assessment.status,
                    "at": assessment.created_at.isoformat()
                    if assessment.created_at
                    else "",
                }
            ],
            errors=[],
        )


@app.get("/assessments/{assessment_id}/documents/{document_name}")
async def get_document(
    assessment_id: str,
    document_name: str,
    user: AuthUser = Depends(require_action(Action.VIEW_ASSESSMENT)),
):
    session_factory = get_async_session_factory()
    async with session_factory() as session:
        from sqlalchemy import select

        stmt = select(AssessmentModel).where(AssessmentModel.id == assessment_id)
        result = await session.execute(stmt)
        assessment = result.scalar_one_or_none()

        if not assessment:
            raise HTTPException(status_code=404, detail="Assessment not found")

        documents = assessment.documents or {}
        if document_name not in documents:
            raise HTTPException(
                status_code=404, detail=f"Document '{document_name}' not found"
            )

        from fastapi.responses import PlainTextResponse

        return PlainTextResponse(
            content=documents[document_name], media_type="text/markdown"
        )


@app.get(
    "/assessments/{assessment_id}/conditions", response_model=list[ConditionResponse]
)
async def list_conditions(
    assessment_id: str,
    status: Optional[str] = None,
    user: AuthUser = Depends(require_action(Action.VIEW_ASSESSMENT)),
):
    session_factory = get_async_session_factory()
    async with session_factory() as session:
        from sqlalchemy import select

        stmt = select(ConditionModel).where(
            ConditionModel.assessment_id == assessment_id
        )
        if status:
            stmt = stmt.where(ConditionModel.status == status)
        stmt = stmt.order_by(ConditionModel.created_at)
        result = await session.execute(stmt)
        conditions = result.scalars().all()

        return [
            ConditionResponse(
                id=c.id,
                assessment_id=c.assessment_id,
                condition_text=c.condition_text,
                source_persona=c.source_persona,
                status=c.status,
                owner=c.owner,
                due_date=c.due_date.isoformat() if c.due_date else None,
                evidence=c.evidence,
                escalation_count=c.escalation_count,
                resolved_by=c.resolved_by,
                resolved_at=c.resolved_at.isoformat() if c.resolved_at else None,
                resolution_notes=c.resolution_notes,
                created_at=c.created_at.isoformat() if c.created_at else "",
                updated_at=c.updated_at.isoformat() if c.updated_at else "",
            )
            for c in conditions
        ]


@app.patch(
    "/assessments/{assessment_id}/conditions/{condition_id}",
    response_model=ConditionResponse,
)
async def transition_condition(
    assessment_id: str,
    condition_id: str,
    req: ConditionTransitionRequest,
    user: AuthUser = Depends(require_action(Action.RESOLVE_CONDITION)),
):
    session_factory = get_async_session_factory()
    async with session_factory() as session:
        from sqlalchemy import select

        stmt = select(ConditionModel).where(
            ConditionModel.id == condition_id,
            ConditionModel.assessment_id == assessment_id,
        )
        result = await session.execute(stmt)
        condition = result.scalar_one_or_none()

        if not condition:
            raise HTTPException(status_code=404, detail="Condition not found")

        if not condition.can_transition(req.status):
            raise HTTPException(
                status_code=409,
                detail=f"Cannot transition condition from {condition.status} to {req.status}. "
                f"Allowed: {ConditionModel.VALID_TRANSITIONS.get(condition.status, set())}",
            )

        condition.status = req.status
        condition.updated_at = datetime.now(timezone.utc)

        if req.owner:
            condition.owner = req.owner
        if req.evidence:
            condition.evidence = req.evidence
        if req.resolution_notes:
            condition.resolution_notes = req.resolution_notes

        if req.status in ("MET", "WAIVED"):
            condition.resolved_by = user.user_id
            condition.resolved_at = datetime.now(timezone.utc)

        await session.commit()
        await session.refresh(condition)

        return ConditionResponse(
            id=condition.id,
            assessment_id=condition.assessment_id,
            condition_text=condition.condition_text,
            source_persona=condition.source_persona,
            status=condition.status,
            owner=condition.owner,
            due_date=condition.due_date.isoformat() if condition.due_date else None,
            evidence=condition.evidence,
            escalation_count=condition.escalation_count,
            resolved_by=condition.resolved_by,
            resolved_at=condition.resolved_at.isoformat()
            if condition.resolved_at
            else None,
            resolution_notes=condition.resolution_notes,
            created_at=condition.created_at.isoformat() if condition.created_at else "",
            updated_at=condition.updated_at.isoformat() if condition.updated_at else "",
        )


@app.post("/conditions/mark-overdue", response_model=int)
async def mark_overdue_conditions(
    user: AuthUser = Depends(require_action(Action.RESOLVE_CONDITION)),
):
    session_factory = get_async_session_factory()
    now = datetime.now(timezone.utc)
    count = 0
    async with session_factory() as session:
        from sqlalchemy import select, and_

        stmt = select(ConditionModel).where(
            and_(
                ConditionModel.status == "OPEN",
                ConditionModel.due_date.isnot(None),
                ConditionModel.due_date < now,
            )
        )
        result = await session.execute(stmt)
        overdue = result.scalars().all()

        for c in overdue:
            if c.can_transition("OVERDUE"):
                c.status = "OVERDUE"
                c.updated_at = now
                c.escalation_count += 1
                count += 1

        await session.commit()

    return count


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _derive_recommendation(result: PipelineResult) -> str:
    blocks = [f for f in result.persona_findings if f.get("rating") == "block"]
    if blocks:
        return "reject"
    concerns = [f for f in result.persona_findings if f.get("rating") == "concern"]
    conditionals = [
        f for f in result.persona_findings if f.get("rating") == "conditional"
    ]
    if concerns:
        return "conditional"
    if conditionals:
        return "conditional"
    return "approve"


# ---------------------------------------------------------------------------
# Quick Scan endpoint
# ---------------------------------------------------------------------------


class QuickScanRequest(BaseModel):
    description: str = Field(
        ..., min_length=10, max_length=5000, description="Business request text"
    )


@app.post("/quick-scan")
async def quick_scan_endpoint(
    req: QuickScanRequest,
    user: AuthUser = Depends(require_action(Action.SUBMIT_REQUEST)),
):
    from preflight.pipeline.quickscan import quick_scan as qs

    result = qs(req.description)
    return {
        "verdict": result.verdict.value,
        "classification": {
            "request_type": result.classification.request_type,
            "impact_level": result.classification.impact_level,
            "confidence": result.classification.confidence,
            "method": result.classification.method,
        },
        "triage": result.triage,
        "perspectives": result.perspectives,
        "red_flags": result.red_flags,
        "warnings": result.warnings,
        "estimated_assessment_time": result.estimated_assessment_time,
        "recommendation": result.recommendation,
    }


# ---------------------------------------------------------------------------
# Clarification questions endpoint
# ---------------------------------------------------------------------------


class ClarificationRequest(BaseModel):
    description: str = Field(
        ..., min_length=10, max_length=5000, description="Business request text"
    )
    perspectives: list[str] = Field(
        default_factory=list, description="Optional perspective IDs to scope questions"
    )


@app.post("/clarify")
async def generate_clarification(
    req: ClarificationRequest,
    user: AuthUser = Depends(require_action(Action.SUBMIT_REQUEST)),
):
    from preflight.pipeline.pipeline import generate_clarification_questions

    questions = generate_clarification_questions(
        request_description=req.description,
        landscape=None,
        perspective_ids=req.perspectives or None,
    )
    return {"questions": questions, "count": len(questions)}


# ---------------------------------------------------------------------------
# Delta re-assessment endpoint
# ---------------------------------------------------------------------------


class DeltaReassessRequest(BaseModel):
    original_assessment_id: str = Field(
        ..., description="ID of the original assessment"
    )
    changes: dict = Field(
        ..., description="What changed in the request (field: new_value)"
    )


@app.post("/assessments/{assessment_id}/reassess")
async def delta_reassess(
    assessment_id: str,
    req: DeltaReassessRequest,
    user: AuthUser = Depends(require_action(Action.RUN_ASSESSMENT)),
):
    from preflight.pipeline.pipeline import determine_delta_reassessment

    session_factory = get_async_session_factory()
    async with session_factory() as session:
        from sqlalchemy import select

        stmt = select(AssessmentModel).where(AssessmentModel.id == assessment_id)
        result = await session.execute(stmt)
        assessment = result.scalar_one_or_none()

        if not assessment:
            raise HTTPException(status_code=404, detail="Assessment not found")

        previous = {
            "request_type": request.request_type
            if (
                request := await session.execute(
                    select(RequestModel).where(RequestModel.id == assessment.request_id)
                )
            ).scalar_one_or_none()
            else "unknown",
            "impact_level": getattr(assessment, "impact_level", "medium"),
            "ratings": {},
            "triage": {
                "treatment": assessment.triage_treatment,
                "reason": assessment.triage_reason or "",
            },
        }

        delta = determine_delta_reassessment(previous, req.changes)

        return {
            "assessment_id": assessment_id,
            "affected_perspectives": delta.get("re_assess", []),
            "carry_forward": delta.get("carry_forward", []),
            "reason": delta.get("reason", ""),
        }


# ---------------------------------------------------------------------------
# Lifecycle state transitions
# ---------------------------------------------------------------------------


class LifecycleTransitionRequest(BaseModel):
    to_state: str = Field(..., description="Target lifecycle state")


LIFECYCLE_STATES = [
    "SUBMITTED",
    "PRELIMINARY",
    "CLARIFICATION",
    "ASSESSED",
    "BOARD_READY",
    "IN_REVIEW",
    "DECIDED",
    "CONDITIONS_OPEN",
    "CLOSED",
]

VALID_TRANSITIONS = {
    "SUBMITTED": {"PRELIMINARY"},
    "PRELIMINARY": {"CLARIFICATION", "ASSESSED"},
    "CLARIFICATION": {"PRELIMINARY", "ASSESSED"},
    "ASSESSED": {"BOARD_READY", "CLARIFICATION"},
    "BOARD_READY": {"IN_REVIEW", "ASSESSED"},
    "IN_REVIEW": {"DECIDED"},
    "DECIDED": {"CONDITIONS_OPEN", "CLOSED"},
    "CONDITIONS_OPEN": {"CONDITIONS_OPEN", "CLOSED"},
    "CLOSED": set(),
}


@app.post("/requests/{request_id}/transition")
async def transition_request_state(
    request_id: str,
    req: LifecycleTransitionRequest,
    user: AuthUser = Depends(require_action(Action.RUN_ASSESSMENT)),
):
    if req.to_state not in LIFECYCLE_STATES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid state: {req.to_state}. Valid: {', '.join(LIFECYCLE_STATES)}",
        )

    session_factory = get_async_session_factory()
    async with session_factory() as session:
        from sqlalchemy import select

        stmt = select(RequestModel).where(RequestModel.id == request_id)
        result = await session.execute(stmt)
        request = result.scalar_one_or_none()

        if not request:
            raise HTTPException(status_code=404, detail="Request not found")

        current_state = request.state
        allowed = VALID_TRANSITIONS.get(current_state, set())

        if req.to_state not in allowed:
            raise HTTPException(
                status_code=409,
                detail=f"Cannot transition from {current_state} to {req.to_state}. "
                f"Allowed: {', '.join(sorted(allowed)) if allowed else 'none (terminal)'}",
            )

        request.state = req.to_state
        request.updated_at = datetime.now(timezone.utc)
        await session.commit()

        return {
            "request_id": request_id,
            "from_state": current_state,
            "to_state": req.to_state,
            "updated_at": request.updated_at.isoformat(),
        }


# ---------------------------------------------------------------------------
# Authority sign-off
# ---------------------------------------------------------------------------


class SignOffRequest(BaseModel):
    action_type: str = Field(
        ..., description="VETO, ESCALATION, INDEPENDENT, or PATIENT_SAFETY"
    )
    persona_name: str = Field(..., description="Name of the authority persona")
    sign_off_status: str = Field(..., description="APPROVED or REJECTED")
    notes: str = Field(default="")


@app.post("/assessments/{assessment_id}/sign-off/{action_id}")
async def sign_off_authority_action(
    assessment_id: str,
    action_id: str,
    req: SignOffRequest,
    user: AuthUser = Depends(require_action(Action.SIGN_OFF_AUTHORITY)),
):
    session_factory = get_async_session_factory()
    async with session_factory() as session:
        from sqlalchemy import select

        stmt = select(AuthorityAction).where(
            AuthorityAction.assessment_id == assessment_id,
            AuthorityAction.id == action_id,
        )
        result = await session.execute(stmt)
        action = result.scalar_one_or_none()

        if not action:
            raise HTTPException(status_code=404, detail="Authority action not found")

        action.sign_off_status = req.sign_off_status
        action.signed_off_by = user.user_id
        action.signed_off_at = datetime.now(timezone.utc)
        action.sign_off_notes = req.notes
        action.updated_at = datetime.now(timezone.utc)

        await session.commit()

        return {
            "action_id": action_id,
            "assessment_id": assessment_id,
            "sign_off_status": action.sign_off_status,
            "signed_off_by": action.signed_off_by,
            "signed_off_at": action.signed_off_at.isoformat(),
        }


# ---------------------------------------------------------------------------
# Board decision recording
# ---------------------------------------------------------------------------


class DecisionItem(BaseModel):
    finding_id: str = Field(..., description="PersonaFinding ID")
    decision: str = Field(
        ..., description="approve | conditional | reject | defer | override"
    )
    reason: str = Field(default="")


class BoardDecisionRequest(BaseModel):
    decision: str = Field(..., description="approve | conditional | reject | defer")
    items: list[DecisionItem] = Field(default_factory=list)
    board_time_actual: str | None = Field(
        default=None, description="Actual board time spent"
    )
    notes: str = Field(default="")


class BoardOverrideRequest(BaseModel):
    finding_id: str = Field(..., description="PersonaFinding ID being overridden")
    original_rating: str = Field(..., description="What the persona said")
    override_decision: str = Field(..., description="What the board decided instead")
    override_reason: str = Field(..., description="Why the board overrode")


@app.post("/assessments/{assessment_id}/decision")
async def record_board_decision(
    assessment_id: str,
    req: BoardDecisionRequest,
    user: AuthUser = Depends(require_action(Action.BOARD_DECISION)),
):
    session_factory = get_async_session_factory()
    async with session_factory() as session:
        from sqlalchemy import select

        stmt = select(AssessmentModel).where(AssessmentModel.id == assessment_id)
        result = await session.execute(stmt)
        assessment = result.scalar_one_or_none()

        if not assessment:
            raise HTTPException(status_code=404, detail="Assessment not found")

        decision = BoardDecisionModel(
            assessment_id=assessment_id,
            decision=req.decision,
            decided_by=user.user_id,
            items=[item.dict() for item in req.items],
            board_time_actual=req.board_time_actual,
            notes=req.notes,
        )
        session.add(decision)

        assessment.status = "DECIDED"
        assessment.updated_at = datetime.now(timezone.utc)

        await session.commit()
        await session.refresh(decision)

        return {
            "decision_id": decision.id,
            "assessment_id": assessment_id,
            "decision": decision.decision,
            "decided_by": decision.decided_by,
            "decided_at": decision.decided_at.isoformat(),
            "items": decision.items,
        }


@app.post("/assessments/{assessment_id}/override")
async def record_board_override(
    assessment_id: str,
    req: BoardOverrideRequest,
    user: AuthUser = Depends(require_action(Action.OVERRIDE_FINDING)),
):
    session_factory = get_async_session_factory()
    async with session_factory() as session:
        from sqlalchemy import select

        stmt = select(AssessmentModel).where(AssessmentModel.id == assessment_id)
        result = await session.execute(stmt)
        assessment = result.scalar_one_or_none()

        if not assessment:
            raise HTTPException(status_code=404, detail="Assessment not found")

        from preflight.db.models import BoardDecision as BoardDecisionModel

        decision_stmt = (
            select(BoardDecisionModel)
            .where(BoardDecisionModel.assessment_id == assessment_id)
            .order_by(BoardDecisionModel.decided_at.desc())
        )
        decision_result = await session.execute(decision_stmt)
        decision = decision_result.scalar_one_or_none()

        if not decision:
            raise HTTPException(
                status_code=409,
                detail="No board decision exists for this assessment. Record a decision first.",
            )

        override = BoardOverrideModel(
            decision_id=decision.id,
            finding_id=req.finding_id,
            original_rating=req.original_rating,
            override_decision=req.override_decision,
            override_reason=req.override_reason,
            overridden_by=user.user_id,
        )
        session.add(override)

        await session.commit()
        await session.refresh(override)

        return {
            "override_id": override.id,
            "assessment_id": assessment_id,
            "decision_id": decision.id,
            "finding_id": req.finding_id,
            "original_rating": override.original_rating,
            "override_decision": override.override_decision,
            "overridden_by": override.overridden_by,
        }


# ---------------------------------------------------------------------------
# Audit log query
# ---------------------------------------------------------------------------


@app.get("/audit", response_model=list[dict])
async def query_audit_log(
    assessment_id: str | None = None,
    event_type: str | None = None,
    limit: int = 100,
    offset: int = 0,
    user: AuthUser = Depends(require_action(Action.EXPORT_AUDIT)),
):
    if not _audit_logger or not isinstance(_audit_logger, MemoryAuditLogger):
        raise HTTPException(
            status_code=501, detail="Audit storage not configured for query"
        )

    entries = _audit_logger.query(
        assessment_id=assessment_id,
        event_type=event_type,
        limit=limit,
        offset=offset,
    )

    return [
        {
            "id": e.id if hasattr(e, "id") else "",
            "timestamp": e.timestamp.isoformat() if hasattr(e, "timestamp") else "",
            "event_type": e.event_type.value
            if hasattr(e, "event_type")
            else str(e.event_type),
            "action": e.action.value if hasattr(e, "action") else str(e.action),
            "actor_id": e.actor_id,
            "actor_role": e.actor_role,
            "resource_type": e.resource_type or "",
            "resource_id": e.resource_id or "",
            "assessment_id": e.assessment_id or "",
            "details": e.details or {},
        }
        for e in entries
    ]
