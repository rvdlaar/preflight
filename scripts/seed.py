"""
Seed the Preflight database with example data for development.

Usage:
    python scripts/seed.py
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from preflight.db.session import init_db, get_async_session_factory
from preflight.db.models import (
    Request,
    Assessment,
    PersonaFinding,
    Condition,
    AuthorityAction,
    BoardDecision,
    User,
)
from preflight.pipeline.quickscan import quick_scan
from preflight.classify.classify import _heuristic_classify


async def seed():
    print("Initializing database...")
    await init_db()

    session_factory = get_async_session_factory()

    async with session_factory() as session:
        architect = User(
            display_name="Rick van der Molen",
            email="rick.vandermolen@ziekenhuis.nl",
            role="chief-architect",
            department="IT",
            clearance_level="confidential",
            clinical_access=True,
            language="nl",
        )
        session.add(architect)
        await session.flush()

        description = (
            "We want to implement Digital Pathology from Sysmex for the pathology lab. "
            "The system will integrate with our existing Cloverleaf integration engine "
            "to exchange patient data and lab results. It needs a PACS connection for "
            "image storage via JiveX."
        )
        classification = _heuristic_classify(description)
        scan = quick_scan(description)

        sample_request = Request(
            external_id="REQ-20260411-001",
            description=description,
            request_type=classification.request_type,
            impact_level=classification.impact_level,
            state="ASSESSED",
            submitted_by=architect.id,
        )
        session.add(sample_request)
        await session.flush()

        assessment = Assessment(
            external_id="PSA-20260411",
            request_id=sample_request.id,
            version=1,
            assessment_mode="fast",
            selected_perspectives=scan.perspectives,
            triage_treatment=scan.triage.get("treatment", "standard-review"),
            triage_reason=scan.triage.get("reason", ""),
            biv_b=3,
            biv_i=3,
            biv_v=2,
        )
        session.add(assessment)
        await session.flush()

        victor = PersonaFinding(
            assessment_id=assessment.id,
            perspective_id="security",
            persona_name="Victor",
            persona_role="Information Security Officer",
            rating="concern",
            authority_type="VETO",
            authority_triggered=True,
            findings=[
                "Data classification includes patient data — NEN 7513 audit logging mandatory",
                "Network segmentation required for clinical data paths",
            ],
            conditions=[
                "DPIA required before processing patient data",
                "NEN 7510 compliance evidence required from vendor",
            ],
        )
        session.add(victor)
        await session.flush()

        aisha = PersonaFinding(
            assessment_id=assessment.id,
            perspective_id="fg-dpo",
            persona_name="Aisha",
            persona_role="Functionaris Gegevensbescherming",
            rating="concern",
            authority_type="INDEPENDENT",
            authority_triggered=True,
            findings=["Processing patient data requires AVG Article 6(1)(e) verification"],
            conditions=["DPIA must be completed before go-live"],
        )
        session.add(aisha)
        await session.flush()

        condition = Condition(
            assessment_id=assessment.id,
            source_finding_id=victor.id,
            condition_text="DPIA must be completed and approved before go-live",
            source_persona="security",
            status="OPEN",
        )
        session.add(condition)

        action = AuthorityAction(
            assessment_id=assessment.id,
            finding_id=victor.id,
            action_type="VETO",
            persona_name="Victor",
            label="Veto — Information Security Officer",
            requires_sign_off="chief-architect",
            sign_off_status="PENDING",
            pipeline_halted=True,
            halt_reason="Patient data requires NEN 7510/7513 compliance verification",
        )
        session.add(action)

        decision = BoardDecision(
            assessment_id=assessment.id,
            decision="CONDITIONAL_APPROVE",
            decided_by=architect.id,
            notes="Approved subject to DPIA completion and NEN 7510 compliance",
        )
        session.add(decision)

        await session.commit()

    print(f"Seeded request: {sample_request.external_id}")
    print(f"Seeded assessment: {assessment.external_id}")
    print(f"Classification: {classification.request_type}/{classification.impact_level}")
    print(f"Quick scan verdict: {scan.verdict.value}")
    print(f"Red flags: {len(scan.red_flags)}")
    print(f"Perspectives: {', '.join(scan.perspectives[:6])}...")
    print("Done!")


if __name__ == "__main__":
    asyncio.run(seed())
