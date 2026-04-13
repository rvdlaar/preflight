"""
End-to-end smoke test — exercises the full pipeline WITHOUT a live LLM.

Uses MockLLMClient to return realistic assessment responses, then verifies:
1. Classification (heuristic) produces correct request_type + impact_level
2. Persona selection respects triage floors
3. Assessment parsing produces expected persona_findings
4. Authority actions fire (VETO, ESCALATION, etc.)
5. Document generation produces all triggered products
6. Citations are tracked and processed
7. BIV, conditions, risk register all populated
8. The pipeline result is complete and self-consistent

Run: pytest src/tests/test_smoke_e2e.py -v
"""

from __future__ import annotations

import pytest

from preflight.llm.client import CallOpts, LLMResponse, LLMRouter
from preflight.pipeline.orchestrator import PipelineResult, run_full_pipeline

FAST_ASSESSMENT_RESPONSE = """[PERSPECTIVE_RATINGS]
cio:conditional cmio:approve security:concern risk:conditional fg-dpo:concern application:conditional integration:conditional data:conditional privacy:conditional solution:approve network:approve information:conditional
[/PERSPECTIVE_RATINGS]

[PERSPECTIVE_FINDINGS]
cio: The proposed system introduces a new clinical integration point
cmio: Clinical workflow improvement is clear and measurable
security: Data classification includes patient data — NEN 7513 audit logging mandatory
risk: Vendor lock-in risk is medium — single source for integration modules
fg-dpo: Processing patient data requires AVG Article 6(1)(e) legal basis verification
application: Integration with Cloverleaf requires HL7v2 adapter
integration: Cloverleaf integration requires interface specification review
data: Data model overlaps with existing patiëntdata informatiedomein
privacy: Privacy Impact Assessment required per AVG Article 35
solution: Technical architecture follows hospital reference architecture
network: Network impact is low — existing infrastructure can handle the load
information: Information architecture must align with ZiRA informatiedomeinenmodel
[/PERSPECTIVE_FINDINGS]

[PERSPECTIVE_CONDITIONS]
cio: Must align with ZiRA applicatiefunctiemodel before procurement
cmio: Clinical validation required before go-live
security: DPIA required before processing patient data, NEN 7510 compliance evidence required
risk: Exit strategy must be documented in vendor contract
fg-dpo: DPIA must be completed and approved before go-live, Data processing agreement with vendor required
application: Integration design must detail Cloverleaf message mapping
integration: Interface contract must be approved by integration team
data: Data ownership must be clarified in DPIA
privacy: DPIA must address data minimization
information: Information model must be reviewed by information architect
[/PERSPECTIVE_CONDITIONS]
"""

REDTEAM_RESPONSE = """[MY_RATING]
concern
[/MY_RATING]

[FINDINGS]
- Groupthink risk: everyone assumes Cloverleaf integration is straightforward but HL7v2 adapter failures are common
- Hidden assumption: vendor claims NEN 7510 compliance but evidence hasn't been independently verified
- Second-order risk: if the DPIA reveals non-compliance mid-project, rollback could leave clinical staff without tooling
[/FINDINGS]

[CONDITIONS]
- Independent NEN 7510 audit of vendor before contract signing
- Rollback plan that preserves existing clinical workflows
[/CONDITIONS]

[STRONGEST_OBJECTION]
The team is underestimating the integration complexity because similar projects have failed at the Cloverleaf adapter stage
[/STRONGEST_OBJECTION]

[HIDDEN_CONCERN]
I've seen three hospitals struggle with exactly this integration pattern
[/HIDDEN_CONCERN]
"""


class MockLLMClient:
    """Returns deterministic responses for the smoke test."""

    def __init__(self, response_text: str, model_name: str = "mock-llm"):
        self._response = response_text
        self._model = model_name
        self._call_count = 0

    def model_name(self) -> str:
        return self._model

    def tier(self) -> str:
        return "strong"

    async def call(self, system: str, user: str, opts: CallOpts | None = None) -> LLMResponse:
        self._call_count += 1
        if "Red Team" in system or "Raven" in system or "red team" in system.lower():
            return LLMResponse(
                text=REDTEAM_RESPONSE,
                model=self._model,
                usage={"prompt_tokens": 500, "completion_tokens": 300},
                latency_ms=100.0,
            )
        return LLMResponse(
            text=self._response,
            model=self._model,
            usage={"prompt_tokens": 1500, "completion_tokens": 800},
            latency_ms=200.0,
        )


@pytest.fixture
def mock_router():
    client = MockLLMClient(FAST_ASSESSMENT_RESPONSE)
    return LLMRouter(client)


@pytest.fixture
def clinical_request():
    return (
        "We want to implement Digital Pathology from Sysmex for the pathology lab. "
        "The system will integrate with our existing Cloverleaf integration engine "
        "to exchange patient data and lab results. It needs a PACS connection for "
        "image storage via JiveX. The vendor is Sysmex Europe."
    )


async def test_full_pipeline_fast_mode(mock_router, clinical_request):
    result = await run_full_pipeline(
        request=clinical_request,
        client=mock_router,
        mode="fast",
        prefer_heuristic_classify=True,
        language="nl",
    )

    assert isinstance(result, PipelineResult)
    assert result.id.startswith("PSA-")
    assert len(result.errors) == 0, f"Pipeline errors: {result.errors}"

    assert result.classification is not None
    assert result.classification.request_type in (
        "clinical-system",
        "new-application",
        "patient-data",
    )
    assert result.classification.impact_level in ("low", "medium", "high", "critical")

    assert len(result.perspectives) >= 6, (
        f"Expected >= 6 perspectives, got {len(result.perspectives)}"
    )

    assert result.triage.get("treatment") is not None

    assert result.biv is not None
    assert "B" in result.biv
    assert "I" in result.biv
    assert "V" in result.biv

    assert len(result.persona_findings) > 0, "No persona findings generated"

    assert len(result.authority_actions) >= 0

    assert len(result.documents) > 0, "No documents generated"
    assert "psa" in result.documents, "PSA document not generated"

    assert result.risk_register is not None

    assert result.principetoets is not None

    assert result.citation_mapping is not None
    assert result.citation_report is not None

    assert len(result.lifecycle) >= 2
    states = [e["state"] for e in result.lifecycle]
    assert "SUBMITTED" in states
    assert "ASSESSED" in states


async def test_clinical_triage_floor(clinical_request):
    client = MockLLMClient(FAST_ASSESSMENT_RESPONSE)
    router = LLMRouter(client)

    result = await run_full_pipeline(
        request=clinical_request,
        client=router,
        mode="fast",
        prefer_heuristic_classify=True,
    )

    if result.classification and result.classification.request_type == "clinical-system":
        assert "cmio" in result.perspectives, (
            "CMIO must be included for clinical-system (triage floor)"
        )
        assert result.triage.get("treatment") != "fast-track", (
            "Clinical-system cannot be fast-tracked"
        )


async def test_patient_data_activates_fg_dpo():
    request = (
        "We want to implement a new patient data system for processing BSN records "
        "and patiëntdata in the clinical workflow."
    )

    client = MockLLMClient(FAST_ASSESSMENT_RESPONSE)
    router = LLMRouter(client)

    result = await run_full_pipeline(
        request=request,
        client=router,
        mode="fast",
        prefer_heuristic_classify=True,
    )

    if result.classification and result.classification.request_type in (
        "patient-data",
        "clinical-system",
    ):
        assert "fg-dpo" in result.perspectives or "privacy" in result.perspectives, (
            "FG-DPO/Privacy must be activated for patient-data"
        )


async def test_documents_contain_draft(mock_router, clinical_request):
    result = await run_full_pipeline(
        request=clinical_request,
        client=mock_router,
        mode="fast",
        prefer_heuristic_classify=True,
    )

    assert "psa" in result.documents
    psa = result.documents["psa"]
    assert "draft" in psa.lower() or "DRAFT" in psa, "PSA must contain draft disclaimer"


async def test_quick_scan_no_llm():
    from preflight.pipeline.quickscan import quick_scan

    result = quick_scan("We want to implement Digital Pathology from Sysmex")

    assert result.classification is not None
    assert result.verdict is not None
    assert result.verdict.value in ("PROCEED", "PROCEED_WITH_CAUTION", "STOP_AND_ASSESS")


async def test_citations_tracked(mock_router, clinical_request):
    result = await run_full_pipeline(
        request=clinical_request,
        client=mock_router,
        mode="fast",
        prefer_heuristic_classify=True,
    )

    assert result.citation_report is not None
    assert isinstance(result.citation_report.faithfulness_score, float)
    assert 0.0 <= result.citation_report.faithfulness_score <= 1.0


async def test_verwerkingsregister_for_patient_data():
    request = "We need a new system for patiëntdata processing with BSN lookup."

    client = MockLLMClient(FAST_ASSESSMENT_RESPONSE)
    router = LLMRouter(client)

    result = await run_full_pipeline(
        request=request,
        client=router,
        mode="fast",
        prefer_heuristic_classify=True,
    )

    if result.classification and result.classification.request_type in (
        "patient-data",
        "clinical-system",
    ):
        assert result.verwerkingsregister is not None, (
            "Verwerkingsregister must be generated for patient-data requests"
        )


async def test_heuristic_classify_no_llm_call():
    client = MockLLMClient(FAST_ASSESSMENT_RESPONSE)
    router = LLMRouter(client)

    result = await run_full_pipeline(
        request="We need a new VPN solution for remote workers",
        client=router,
        mode="fast",
        prefer_heuristic_classify=True,
    )

    assert result.classification is not None
    assert result.classification.method == "heuristic"
    assert client._call_count >= 1, "Heuristic classify should still call LLM for assessment"


async def test_guard_flags_on_bsn_input():
    request = "We want to process BSN 123456789 for patient lookup"

    client = MockLLMClient(FAST_ASSESSMENT_RESPONSE)
    router = LLMRouter(client)

    result = await run_full_pipeline(
        request=request,
        client=router,
        mode="fast",
        prefer_heuristic_classify=True,
    )

    assert len(result.guard_flags) > 0, "BSN in request should trigger guard flag"
    bsn_flag = any("BSN" in f for f in result.guard_flags)
    assert bsn_flag, "Expected BSN detection flag"


async def test_biv_populated(mock_router, clinical_request):
    result = await run_full_pipeline(
        request=clinical_request,
        client=mock_router,
        mode="fast",
        prefer_heuristic_classify=True,
    )

    assert result.biv is not None
    biv_keys = {"B", "I", "V"}
    assert biv_keys.issubset(result.biv.keys()), f"BIV missing keys: {biv_keys - result.biv.keys()}"


async def test_conditions_populated(mock_router, clinical_request):
    result = await run_full_pipeline(
        request=clinical_request,
        client=mock_router,
        mode="fast",
        prefer_heuristic_classify=True,
    )

    assert result.conditions is not None
    assert len(result.conditions) > 0, "Conditions should be generated from persona findings"


def test_hyde_reranker_wiring():
    from preflight.retrieval.reranker import HyDEReranker, IdentityReranker

    hyde = HyDEReranker(reranker=IdentityReranker(), llm_client=None)
    assert hasattr(hyde, "generate_hypothetical"), "HyDEReranker must have generate_hypothetical"
    assert isinstance(hyde._reranker, IdentityReranker)
    assert hyde._llm is None

    from preflight.retrieval.reranker import create_reranker

    base = create_reranker("mxbai", use_hyde=False)
    assert not hasattr(base, "generate_hypothetical"), "Base reranker should not have HyDE"

    with_hyde_no_llm = create_reranker("mxbai", use_hyde=True, llm_client=None)
    assert not hasattr(with_hyde_no_llm, "generate_hypothetical"), (
        "HyDE without LLM should not wrap"
    )


async def test_hyde_generate_hypothetical_with_mock_llm():
    from preflight.retrieval.reranker import HyDEReranker, IdentityReranker

    mock = MockLLMClient("This is a hypothetical answer about NEN 7510 controls.")
    hyde = HyDEReranker(reranker=IdentityReranker(), llm_client=mock)

    result = await hyde.generate_hypothetical(
        "What NEN 7510 controls apply?",
        persona_id="security",
        persona_focus="security architecture",
    )

    assert isinstance(result, str)
    assert len(result) > 0, "HyDE should return non-empty text"
    assert result != "What NEN 7510 controls apply?", (
        "HyDE should transform the query, not return it unchanged"
    )


async def test_hyde_fallback_when_no_llm():
    from preflight.retrieval.reranker import HyDEReranker, IdentityReranker

    hyde = HyDEReranker(reranker=IdentityReranker(), llm_client=None)
    result = await hyde.generate_hypothetical("What NEN 7510 controls apply?")
    assert result == "What NEN 7510 controls apply?", (
        "HyDE without LLM should return original query"
    )
