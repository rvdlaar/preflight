"""
Preflight pipeline orchestrator — async Steps 0-5 wired end-to-end.

This is the main entry point that glues together:
  Step 0: Landscape context (ArchiMate parser)
  Step 1: Classification (LLM or heuristic → request_type + impact_level)
  Step 2: Persona selection + per-persona RAG retrieval (ROUTING + triage floors)
  Step 3: Assessment (LLM call — fast mode or deep mode, with retrieved context)
  Step 4: Authority challenge (Victor/Nadia/FG-DPO/CMIO/Raven)
  Step 5: Output (documents, diagrams, risk register, conditions + citation report)

Uses the synchronous synthesis pipeline for Steps 2/4/5 and the LLM for
Steps 1 and 3. Step 2 now includes per-persona RAG retrieval when a vector
store is configured.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from typing import Any

from preflight.auth.guardrails import scan_input
from preflight.auth.hooks import (
    GuardrailRegistry,
    HookPoint,
    create_default_registry,
)
from preflight.citation.processor import (
    CitationMapping,
    CitationMode,
    CitationProcessor,
)
from preflight.citation.verify import CitationReport, build_citation_report
from preflight.classify.classify import (
    ClassificationResult,
    DualClassificationResult,
    _heuristic_classify,
    classify_request,
    classify_request_dual,
    select_relevant_perspectives,
)
from preflight.llm.client import CallOpts, LLMRouter
from preflight.llm.parser import parse_deep_assessment, parse_fast_assessment
from preflight.llm.prompt import (
    CITATION_CONSTRAINT,
    PERSONA_VERSION,
    PERSPECTIVES,
    build_deep_assessment_prompt,
    build_fast_assessment_prompt,
)
from preflight.llm.prompt import (
    persona_hash as compute_persona_hash,
)
from preflight.pipeline.pipeline import (
    apply_triage_floors,
    citation_constraint_prompt,
    create_conditions,
    deduplicate_findings,
    derive_biv_controls,
    determine_biv,
    generate_citation_appendix,
    generate_clarification_questions,
    generate_principetoets,
    generate_risk_register,
    generate_verwerkingsregister_draft,
    process_authority_actions,
)
from preflight.retrieval.retrieve import (
    PersonaContext,
    build_retrieved_context_for_prompt,
    retrieve_per_persona,
)
from preflight.retrieval.store import VectorStoreClient
from preflight.model.types import ArchiMateModel
from preflight.synthesis.diagrams import generate_diagrams
from preflight.synthesis.docgen import build_document_context, render_all_documents

# ---------------------------------------------------------------------------
# Pipeline result
# ---------------------------------------------------------------------------


@dataclass
class PipelineResult:
    id: str = ""
    classification: ClassificationResult | None = None
    perspectives: list[str] = field(default_factory=list)
    triage: dict = field(default_factory=dict)
    authority_actions: list[dict] = field(default_factory=list)
    biv: dict = field(default_factory=dict)
    biv_controls: list[dict] | dict = field(default_factory=dict)
    persona_findings: list[dict] = field(default_factory=list)
    documents: dict[str, str] = field(default_factory=dict)
    diagrams: dict[str, dict] = field(default_factory=dict)
    conditions: list[dict] = field(default_factory=list)
    principetoets: dict | list[dict] = field(default_factory=dict)
    deduplicated: list[dict] = field(default_factory=list)
    risk_register: str | list[dict] = ""
    citation_appendix: str = ""
    llm_constraint: str = ""
    lifecycle: list[dict] = field(default_factory=list)
    raw_llm_output: str = ""
    errors: list[str] = field(default_factory=list)
    persona_contexts: list[PersonaContext] = field(default_factory=list)
    retrieved_context: dict[str, str] = field(default_factory=dict)
    citation_report: CitationReport | None = None
    persona_version: str = "1.0.0"
    persona_hash: str = ""
    verwerkingsregister: dict | None = None
    clarification_questions: list[dict] = field(default_factory=list)
    zira_conflicts: list[dict] = field(default_factory=list)
    language: str = "nl"
    citation_mapping: CitationMapping = field(default_factory=CitationMapping)
    guard_flags: list[str] = field(default_factory=list)
    archimate_model: ArchiMateModel | None = None


# ---------------------------------------------------------------------------
# Step 1: Classify
# ---------------------------------------------------------------------------


async def step_classify(
    request: str,
    client: LLMRouter | Any,
    landscape_context: dict | None = None,
    prefer_heuristic: bool = False,
    dual: bool = False,
) -> ClassificationResult | DualClassificationResult:
    if prefer_heuristic:
        return _heuristic_classify(request)
    if dual:
        return await classify_request_dual(client, request, landscape_context)
    return await classify_request(client, request, landscape_context)


AUTHORITY_PERSONAS = {"security", "risk", "fg-dpo", "cmio"}


def _select_client_for_persona(router: LLMRouter | Any, perspective_id: str) -> Any:
    """Route authority personas to strong/frontier model, others to light model."""
    if not isinstance(router, LLMRouter):
        return router
    if perspective_id in AUTHORITY_PERSONAS:
        return router.frontier() if router.frontier() != router.strong() else router.strong()
    return router.light()


async def step_assess(
    client: LLMRouter | Any,
    perspectives: list[str],
    request: str,
    landscape_context: dict | str | None = None,
    mode: str = "fast",
    sources: list[str] | None = None,
    retrieved_context: dict[str, str] | None = None,
    interaction_rounds: int = 2,
) -> list[dict]:
    """Step 3: Run LLM assessment for selected perspectives.

    Fast mode: single batched call with all perspectives (uses strong model).
    Deep mode: per-persona calls with interaction rounds (routes per persona).
    Authority personas (security, risk, fg-dpo, cmio) use frontier/strong model.
    """
    fast_client = client.strong() if isinstance(client, LLMRouter) else client

    landscape_context_str = (
        "\n".join(f"- {k}: {v}" for k, v in landscape_context.items())
        if isinstance(landscape_context, dict)
        else str(landscape_context or "")
    ) or None

    if mode == "deep" and len(perspectives) > 1:
        per_persona_landscape = _scope_landscape_per_persona(landscape_context)
        return await _deep_assess(
            client,
            perspectives,
            request,
            landscape_context_str,
            sources,
            retrieved_context,
            interaction_rounds,
            per_persona_landscape,
        )

    system_prompt, user_prompt = build_fast_assessment_prompt(
        request_description=request,
        selected_perspective_ids=perspectives,
        landscape_context=landscape_context_str,
        retrieved_context=retrieved_context or None,
    )

    opts = CallOpts(temperature=0.3, max_tokens=4096, retries=2)
    response = await fast_client.call(system_prompt, user_prompt, opts)

    parsed = parse_fast_assessment(response.text)

    perspective_map = {p["id"]: p for p in PERSPECTIVES}

    findings: list[dict] = []
    for r in parsed.ratings:
        persona = perspective_map.get(r.perspective_id, {})
        findings.append(
            {
                "perspective_id": r.perspective_id,
                "name": persona.get("label", r.perspective_id),
                "role": persona.get("role", r.perspective_id),
                "focus": persona.get("focus", ""),
                "rating": r.rating,
                "findings": [r.reason] if r.reason else [],
                "conditions": r.conditions,
                "authority": persona.get("authority"),
            }
        )

    if not findings and parsed.unparsed:
        findings.append(
            {
                "perspective_id": "unknown",
                "name": "Unknown",
                "role": "Unknown",
                "focus": "",
                "rating": "conditional",
                "findings": [f"Parse failed — raw output: {parsed.unparsed[:500]}"],
                "conditions": [],
                "parse_confidence": parsed.parse_confidence,
            }
        )

    return findings


LANDSCAPE_SCOPE_MAP: dict[str, list[str]] = {
    "cio": ["existingApps", "capabilityMap", "techRadarStatus"],
    "cmio": ["capabilityMap", "raw"],
    "chief": ["existingApps", "capabilityMap", "cascadeDeps"],
    "business": ["capabilityMap", "existingApps"],
    "process": ["capabilityMap", "relatedInterfaces"],
    "application": ["existingApps", "techRadarStatus", "cascadeDeps"],
    "integration": ["relatedInterfaces", "raw"],
    "infrastructure": ["techRadarStatus", "cascadeDeps"],
    "data": ["openRisks", "raw"],
    "security": ["openRisks", "relatedInterfaces", "cascadeDeps"],
    "ciso": ["openRisks", "cascadeDeps"],
    "iso-officer": ["openRisks", "techRadarStatus"],
    "risk": ["openRisks", "cascadeDeps"],
    "fg-dpo": ["openRisks", "raw"],
    "privacy": ["openRisks", "raw"],
    "solution": ["existingApps", "relatedInterfaces"],
    "information": ["capabilityMap", "raw"],
    "network": ["relatedInterfaces", "cascadeDeps"],
    "portfolio": ["existingApps", "techRadarStatus", "capabilityMap"],
    "manufacturing": ["cascadeDeps", "relatedInterfaces"],
    "rnd": ["capabilityMap", "techRadarStatus"],
    "redteam": ["openRisks", "cascadeDeps", "relatedInterfaces"],
}


def _scope_landscape_per_persona(
    landscape_context: dict | str | None,
) -> dict[str, str]:
    """Create per-persona landscape context strings from a flat dict.

    Returns {persona_id: formatted_landscape_string} where each persona
    only sees the landscape keys relevant to their domain.
    """
    if not landscape_context or not isinstance(landscape_context, dict):
        return {}

    result = {}
    for pid, scope_keys in LANDSCAPE_SCOPE_MAP.items():
        parts = []
        for key in scope_keys:
            val = landscape_context.get(key)
            if val:
                if isinstance(val, list):
                    val = ", ".join(str(v) for v in val[:15])
                parts.append(f"{key}: {val}")
        if parts:
            result[pid] = "\n".join(parts)

    return result


async def _deep_assess(
    client: LLMRouter | Any,
    perspectives: list[str],
    request: str,
    landscape_context: str | None,
    sources: list[str] | None,
    retrieved_context: dict[str, str] | None,
    interaction_rounds: int = 2,
    per_persona_landscape: dict[str, str] | None = None,
) -> list[dict]:
    """Deep mode: per-persona LLM calls with interaction rounds.

    Authority personas (security, risk, fg-dpo, cmio) use frontier/strong model.
    Other personas use light model for cost efficiency.
    """
    all_findings: list[dict] = []

    persona_map = {p["id"]: p for p in PERSPECTIVES if p["id"] in perspectives}

    # Round 1: Independent assessment per persona (with per-persona routing)
    round1_findings: dict[str, dict] = {}
    for pid in perspectives:
        persona = persona_map.get(pid, {"id": pid, "label": pid, "role": pid, "focus": ""})
        persona_client = _select_client_for_persona(client, pid)
        persona_landscape = (
            per_persona_landscape.get(pid, landscape_context)
            if per_persona_landscape
            else landscape_context
        )
        persona_context_str = retrieved_context.get(pid, "") if retrieved_context else None
        system_prompt, user_prompt = build_deep_assessment_prompt(
            persona=persona,
            request_description=request,
            landscape_context=persona_landscape,
            retrieved_context=persona_context_str,
        )
        opts = CallOpts(temperature=0.2, max_tokens=2048, retries=1)
        try:
            response = await persona_client.call(system_prompt, user_prompt, opts)
            parsed = parse_deep_assessment(response.text, pid)
            round1_findings[pid] = {
                "perspective_id": pid,
                "name": persona.get("label", pid),
                "role": persona.get("role", pid),
                "focus": persona.get("focus", ""),
                "rating": parsed.rating,
                "findings": parsed.findings,
                "conditions": parsed.conditions,
                "authority": parsed.authority,
                "strongest_objection": parsed.strongest_objection,
                "hidden_concern": parsed.hidden_concern,
                "interaction_round": 1,
            }
        except Exception as e:
            logging.getLogger(__name__).warning(f"Deep assessment failed for {pid}: {e}")
            round1_findings[pid] = {
                "perspective_id": pid,
                "name": persona.get("label", pid),
                "role": persona.get("role", pid),
                "rating": "na",
                "findings": [],
                "conditions": [],
                "interaction_round": 1,
            }

    # Interaction rounds 2+: each persona sees others' key findings and may revise
    current_findings = dict(round1_findings)
    for round_num in range(2, interaction_rounds + 1):
        other_summary = "\n".join(
            f"- {f.get('name', f['perspective_id'])} ({f.get('rating', 'na')}): "
            + "; ".join(f.get("findings", [])[:3])
            + (f" [revised: {f.get('revised_rating', '?')}]" if f.get("revised_rating") else "")
            for f in current_findings.values()
            if f.get("findings")
        )

        for pid, cf in current_findings.items():
            persona = persona_map.get(pid, {"id": pid, "label": pid, "role": pid})
            current_rating = cf.get("revised_rating", cf.get("rating", "na"))
            current_findings_list = cf.get("revised_findings", cf.get("findings", []))
            revise_system = (
                f"You are {persona.get('label', pid)}, {persona.get('role', pid)} in the EA council. "
                f"You assessed this proposal as '{current_rating}'. "
                "Other board members have shared their findings. "
                "Review their key points and decide if you want to revise your assessment."
            )
            revise_user = (
                f"Proposal: {request}\n\n"
                f"Your current assessment: {current_rating} — "
                f"{'; '.join(current_findings_list[:3])}\n\n"
                f"Other board members' findings:\n{other_summary}\n\n"
                "Do you revise your rating, findings, or conditions? "
                "Respond with: RATING | FINDINGS | CONDITIONS | any revisions."
            )
            opts = CallOpts(temperature=0.2, max_tokens=2048, retries=1)
            try:
                persona_client = _select_client_for_persona(client, pid)
                response = await persona_client.call(revise_system, revise_user, opts)
                revised = parse_deep_assessment(response.text, pid)
                if revised and (revised.findings or revised.rating != "na"):
                    cf["interaction_round"] = round_num
                    if revised.rating and revised.rating != "na":
                        cf["revised_rating"] = revised.rating
                    if revised.findings:
                        cf["revised_findings"] = revised.findings
                    if revised.conditions:
                        cf["revised_conditions"] = revised.conditions
            except Exception as e:
                logging.getLogger(__name__).debug(
                    f"Revision round {round_num} failed for {pid}: {e}"
                )

    all_findings.extend(current_findings.values())
    return all_findings


async def step_redteam_challenge(
    client: LLMRouter | Any,
    persona_findings: list[dict],
    request: str,
    mode: str = "fast",
) -> dict | None:
    """Step 4d: Red Team pre-mortem.

    Raven reviews all other personas' findings and looks for:
    - Groupthink patterns
    - Hidden assumptions
    - Second-order risks
    - Failure scenarios

    Uses frontier model for challenge — this is the most critical review.
    """
    challenge_client = client.frontier() if isinstance(client, LLMRouter) else client

    findings_summary = "\n".join(
        f"- {pf.get('name', pf.get('perspective_id', '?'))} "
        f"({pf.get('rating', '?')}): " + "; ".join(pf.get("findings", [])[:3])
        for pf in persona_findings
        if pf.get("name") != "Raven"
    )

    system_prompt = (
        "You are Raven, the Red Team Challenge persona on the EA council. "
        "Your role is to find groupthink, hidden assumptions, second-order risks, "
        "and failure scenarios that the other board members may have missed.\n\n"
        "Think like a pre-mortem: assume the project FAILED. What went wrong? "
        "What did everyone assume that wasn't true? What cascading failures could occur?\n\n"
        + CITATION_CONSTRAINT
        + "\n\n"
        "Rate: concern | conditional | block\n"
        "List findings and conditions.\n\n"
        "Use this format:\n"
        "[MY_RATING]\nconcern | conditional | block\n[/MY_RATING]\n\n"
        "[FINDINGS]\n- finding 1\n- finding 2\n[/FINDINGS]\n\n"
        "[CONDITIONS]\n- condition 1\n- condition 2\n[/CONDITIONS]\n\n"
        "[STRONGEST_OBJECTION]\nyour strongest objection\n[/STRONGEST_OBJECTION]\n\n"
        "[HIDDEN_CONCERN]\nwhat you're thinking but won't say\n[/HIDDEN_CONCERN]"
    )

    user_prompt = (
        f"Proposal: {request}\n\n"
        f"Other board members' findings:\n{findings_summary}\n\n"
        "Perform a Red Team challenge. What groupthink do you see? "
        "What assumptions might be wrong? What could cascade into failure?"
    )

    opts = CallOpts(temperature=0.4, max_tokens=2048, retries=1)
    try:
        response = await challenge_client.call(system_prompt, user_prompt, opts)
        parsed = parse_deep_assessment(response.text, "redteam")
        if parsed and parsed.rating in ("concern", "conditional", "block"):
            return {
                "perspective_id": "redteam",
                "name": "Raven",
                "role": "Red Team Challenge",
                "rating": parsed.rating,
                "findings": parsed.findings,
                "conditions": parsed.conditions,
                "authority": "CHALLENGE",
                "strongest_objection": parsed.strongest_objection,
                "hidden_concern": parsed.hidden_concern,
            }
    except Exception as e:
        logging.getLogger(__name__).warning(f"Red Team challenge failed: {e}")

    return None


# ---------------------------------------------------------------------------
# Full pipeline
# ---------------------------------------------------------------------------


def step_select_perspectives(
    classification: ClassificationResult,
) -> list[str]:
    return select_relevant_perspectives(classification.request_type, classification.impact_level)


# ---------------------------------------------------------------------------
# Step 2b: Retrieve (per-persona RAG)
# ---------------------------------------------------------------------------


async def step_retrieve(
    request: str,
    perspectives: list[str],
    embedding_router: Any | None = None,
    store: VectorStoreClient | None = None,
    reranker: Any | None = None,
    use_hyde: bool = False,
) -> tuple[list[PersonaContext], dict[str, str]]:
    try:
        persona_contexts = await retrieve_per_persona(
            request=request,
            selected_perspectives=perspectives,
            embedding_router=embedding_router,
            store=store,
            reranker=reranker,
            use_hyde=use_hyde,
        )
        retrieved = build_retrieved_context_for_prompt(persona_contexts)
        return persona_contexts, retrieved
    except Exception as e:
        import logging

        logging.getLogger(__name__).warning(f"Retrieval failed, continuing without context: {e}")
        return [], {}


async def run_full_pipeline(
    request: str,
    client: LLMRouter | Any,
    landscape_context: dict | None = None,
    zira: dict | None = None,
    sources: list[str] | None = None,
    mode: str = "fast",
    prefer_heuristic_classify: bool = False,
    dual_classify: bool | None = None,
    submitted_by: str = "",
    embedding_router: Any | None = None,
    vector_store: VectorStoreClient | None = None,
    reranker: Any | None = None,
    use_hyde: bool = False,
    language: str = "nl",
    interaction_rounds: int = 2,
    guard_hooks: GuardrailRegistry | None = None,
) -> PipelineResult:
    result = PipelineResult(
        id=f"PSA-{date.today().strftime('%Y%m%d')}",
        lifecycle=[{"state": "SUBMITTED", "at": datetime.now(timezone.utc).isoformat()}],
        persona_version=PERSONA_VERSION,
        persona_hash=compute_persona_hash(),
        language=language,
    )

    hooks = guard_hooks or create_default_registry()

    # Step 0: Input guardrails — scan for BSN, patient IDs, injection
    guard_result = scan_input(request)
    hook_result = hooks.run_hooks(
        HookPoint.PRE_CLASSIFY,
        request,
        context={"submitted_by": submitted_by},
    )
    request = hook_result.text
    if guard_result.flags:
        result.errors.extend(guard_result.flags)
    if hook_result.flags:
        result.guard_flags.extend(hook_result.flags)

    # Step 1: Classify (auto-dual for high/critical when dual_classify is None)
    use_dual = dual_classify if dual_classify is not None else False

    if not use_dual and not prefer_heuristic_classify:
        try:
            quick_classify = await classify_request(client, request, landscape_context)
            if quick_classify.impact_level in ("high", "critical"):
                use_dual = True
                result.lifecycle.append(
                    {
                        "state": "DUAL_CLASSIFY_TRIGGERED",
                        "at": datetime.now(timezone.utc).isoformat(),
                        "reason": f"Auto-dual for impact={quick_classify.impact_level}",
                    }
                )
        except Exception as e:
            logging.getLogger(__name__).debug(f"Auto-dual classification skipped: {e}")

    try:
        classification_result = await step_classify(
            request,
            client,
            landscape_context,
            prefer_heuristic_classify,
            dual=use_dual,
        )
    except Exception as e:
        result.errors.append(f"Classification failed: {e}")
        classification_result = _heuristic_classify(request)

    if isinstance(classification_result, DualClassificationResult):
        classification = classification_result.merged
        if not classification_result.agreement:
            result.errors.insert(
                0,
                (
                    f"DUAL CLASSIFICATION DISAGREEMENT: "
                    f"{classification_result.divergence_detail}. "
                    f"Using primary classification but flag for architect review."
                ),
            )
    else:
        classification = classification_result

    result.classification = classification

    request_type = classification.request_type
    impact_level = classification.impact_level

    # Step 2: Select perspectives + triage floors
    perspectives = step_select_perspectives(classification)
    result.perspectives = perspectives

    _DEFAULT_TREATMENT = {
        "low": "fast-track",
        "medium": "standard-review",
        "high": "standard-review",
        "critical": "deep-review",
    }
    default_treatment = _DEFAULT_TREATMENT.get(impact_level, "standard-review")
    triage = {"treatment": default_treatment, "reason": f"Default for {impact_level} impact"}
    perspectives, triage = apply_triage_floors(
        request_type, impact_level, perspectives, triage, request_text=request
    )
    result.triage = triage

    # Step 2b: Per-persona RAG retrieval (with optional reranker + HyDE)
    persona_contexts, retrieved_context = await step_retrieve(
        request,
        perspectives,
        embedding_router,
        vector_store,
        reranker=reranker,
        use_hyde=use_hyde,
    )
    result.persona_contexts = persona_contexts
    result.retrieved_context = retrieved_context

    # Step 3: Assess (LLM) — with retrieved context if available
    try:
        persona_findings = await step_assess(
            client,
            perspectives,
            request,
            landscape_context,
            mode,
            sources,
            retrieved_context=retrieved_context or None,
            interaction_rounds=interaction_rounds,
        )
        result.persona_findings = persona_findings
        for pf in persona_findings:
            pf["persona_version"] = PERSONA_VERSION
    except Exception as e:
        result.errors.append(f"Assessment failed: {e}")
        persona_findings = []

    # Step 4: Authority challenge (built into persona_findings processing)
    result.authority_actions = process_authority_actions(persona_findings)

    # Step 4d: Red Team pre-mortem (Raven reviews other personas' findings)
    has_veto_or_escalation = any(
        a.get("triggered") and a.get("type") in ("VETO", "ESCALATION", "INDEPENDENT")
        for a in result.authority_actions
    )
    if "redteam" in perspectives and not has_veto_or_escalation:
        try:
            challenge_findings = await step_redteam_challenge(
                client, persona_findings, request, mode
            )
            if challenge_findings:
                persona_findings.append(challenge_findings)
                result.authority_actions.append(
                    {
                        "type": "CHALLENGE",
                        "persona": "Raven",
                        "label": "Red Team Pre-Mortem",
                        "triggered": True,
                        "requires_sign_off": "chief-architect",
                        "sign_off_status": "PENDING",
                        "findings": challenge_findings.get("findings", []),
                        "conditions": challenge_findings.get("conditions", []),
                        "draft_disclaimer": (
                            "This is a DRAFT Red Team challenge generated by Preflight. "
                            "The chief architect must review before board presentation."
                        ),
                    }
                )
        except Exception as e:
            result.errors.append(f"Red Team challenge failed: {e}")

    # Step 1b: Generate clarification questions for missing context
    try:
        result.clarification_questions = generate_clarification_questions(
            request, landscape_context, perspectives
        )
    except Exception as e:
        result.errors.append(f"Clarification generation failed: {e}")

    # Step 0b: ZiRA conflict detection (if ArchiMate model provided)
    if landscape_context and landscape_context.get("archi_model"):
        try:
            from preflight.archimate.zira import detect_zira_conflicts

            archi_model = landscape_context["archi_model"]
            zira_model = landscape_context.get("zira_model")
            if zira_model:
                result.zira_conflicts = detect_zira_conflicts(archi_model, zira_model)
        except Exception as e:
            result.errors.append(f"ZiRA conflict detection failed: {e}")

    # Step 5: Output synthesis
    ratings = {
        pf.get(
            "perspective_id",
            pf.get("name", "").lower().replace(" ", "").replace("-", ""),
        ): pf.get("rating", "na")
        for pf in persona_findings
    }

    biv = determine_biv(persona_findings, request_type)
    result.biv = biv
    result.biv_controls = derive_biv_controls(biv)

    conditions = create_conditions(persona_findings, result.id, biv_controls=result.biv_controls)
    result.conditions = conditions

    principetoets = generate_principetoets(persona_findings)
    result.principetoets = principetoets

    if request_type in ("patient-data", "clinical-system") or any(
        kw in request.lower()
        for kw in (
            "patient data",
            "patiëntdata",
            "persoonsgegevens",
            "bsn",
            "zorggegevens",
        )
    ):
        result.verwerkingsregister = generate_verwerkingsregister_draft(
            proposal_name=request[:100],
            processing_description=f"Verwerking van persoonsgegevens in het kader van: {request[:200]}",
            purpose=f"Ondersteuning van {request_type} in het zorgproces",
            legal_basis="AVG Artikel 6 lid 1 sub e — verwerking is noodzakelijk voor de uitvoering van een taak in het algemeen belang of van een taak in het kader van de uitoefening van het openbare gezag",
            data_subjects=["Patiënten", "Medewerkers"],
            retention_period="Maximaal bewaartermijn conform NEN 7510 en WGBO",
            persona_findings=persona_findings,
        )

    deduplicated = deduplicate_findings(persona_findings)
    result.deduplicated = deduplicated

    docgen_context = build_document_context(
        proposal_name=request,
        request_type=request_type,
        impact_level=impact_level,
        classification=result.classification,
        persona_findings=persona_findings,
        ratings={pid: ratings.get(pid, "na") for pid in perspectives},
        triage=triage,
        biv=biv,
        biv_controls=result.biv_controls,
        conditions=result.conditions,
        principetoets=result.principetoets,
        authority_actions=result.authority_actions,
        landscape=landscape_context,
        zira=zira,
        assessment_mode=mode,
        language=language,
        citation_mapping=result.citation_mapping,
    )
    documents = render_all_documents(docgen_context)
    result.documents = documents

    result.diagrams = generate_diagrams(
        {
            "request_type": request_type,
            "ratings": ratings,
            "proposedApp": {"name": request},
            "existingApps": (landscape_context or {}).get("existingApps", []),
            "integrations": (landscape_context or {}).get("raw", {}).get("interfaces", []),
            "dataObjects": (landscape_context or {}).get("raw", {}).get("dataObjects", []),
            "biv": biv,
            "zira": zira or {},
        }
    )

    try:
        from preflight.model.builder import build_model
        from preflight.model.review import generate_review, generate_corrections_yaml
        from preflight.model.exchange import write_exchange_file
        from pathlib import Path

        archimate_model = build_model(result)
        result.archimate_model = archimate_model

        output_dir = Path("output") / result.id
        output_dir.mkdir(parents=True, exist_ok=True)

        review_path = output_dir / f"{result.id}-model-review.md"
        review_path.write_text(generate_review(archimate_model), encoding="utf-8")

        corrections_path = output_dir / f"{result.id}-corrections.yaml"
        corrections_path.write_text(generate_corrections_yaml(archimate_model), encoding="utf-8")

        archimate_path = output_dir / f"{result.id}-preflight.archimate"
        write_exchange_file(archimate_model, str(archimate_path))
    except Exception as e:
        logging.getLogger(__name__).warning(f"ArchiMate model generation failed: {e}")
        result.errors.append(f"ArchiMate model generation failed: {e}")

    result.risk_register = generate_risk_register(persona_findings)
    result.citation_appendix = generate_citation_appendix(persona_findings, sources or [])
    result.llm_constraint = citation_constraint_prompt(persona_findings, sources or [])

    # Process citations through CitationProcessor for accumulation and attribution
    citation_proc = CitationProcessor(mode=CitationMode.KEEP_MARKERS)
    for pf in persona_findings:
        pid = pf.get("perspective_id", "")
        for i, finding in enumerate(pf.get("findings", [])):
            finding_text = finding if isinstance(finding, str) else finding.get("finding", "")
            processed, _ = citation_proc.process(finding_text, persona_id=pid)
            if isinstance(pf["findings"][i], dict):
                pf["findings"][i]["finding"] = processed
            else:
                pf["findings"][i] = processed
        for i, cond in enumerate(pf.get("conditions", [])):
            cond_text = cond if isinstance(cond, str) else cond.get("condition", "")
            processed, _ = citation_proc.process(cond_text, persona_id=pid)
            if isinstance(pf["conditions"][i], dict):
                pf["conditions"][i]["condition"] = processed
            else:
                pf["conditions"][i] = processed
    result.citation_mapping = citation_proc.mapping

    # Citation verification against retrieved sources
    all_source_ids = list(set(sid for pc in result.persona_contexts for sid in pc.source_ids))

    known_persona_ids = [p["id"] for p in PERSPECTIVES]
    known_sources = set(all_source_ids) if all_source_ids else None
    result.citation_report = build_citation_report(
        persona_findings=persona_findings,
        known_personas=known_persona_ids,
        known_sources=known_sources,
        retrieved_source_ids=all_source_ids,
    )

    # Post-output guardrail hook (NEN 7513 audit logging)
    for doc_name, doc_text in result.documents.items():
        hook_result = hooks.run_hooks(
            HookPoint.POST_OUTPUT,
            doc_text,
            context={
                "assessment_id": result.id,
                "document": doc_name,
                "user_id": submitted_by,
            },
            is_authority=False,
        )
        if hook_result.flags:
            result.guard_flags.extend(hook_result.flags)

    result.lifecycle.append({"state": "ASSESSED", "at": datetime.now(timezone.utc).isoformat()})

    return result


# ---------------------------------------------------------------------------
# Convenience: run pipeline from just a request string (heuristic classify)
# ---------------------------------------------------------------------------


async def assess(
    request: str,
    client: LLMRouter | Any,
    mode: str = "fast",
    landscape_context: dict | None = None,
    zira: dict | None = None,
    embedding_router: Any | None = None,
    vector_store: VectorStoreClient | None = None,
    reranker: Any | None = None,
    use_hyde: bool = False,
    language: str = "nl",
) -> PipelineResult:
    return await run_full_pipeline(
        request=request,
        client=client,
        landscape_context=landscape_context,
        zira=zira,
        mode=mode,
        embedding_router=embedding_router,
        vector_store=vector_store,
        reranker=reranker,
        use_hyde=use_hyde,
        language=language,
    )
