"""Tests for deep mode, board decisions, SIEM forwarding, condition APIs,
verwerkingsregister extraction, integration clients, and parser fixes."""

from preflight.llm.parser import parse_deep_assessment
from preflight.pipeline.pipeline import (
    generate_verwerkingsregister_draft,
    _extract_data_categories,
    _extract_data_subjects,
    _extract_legal_basis,
    _extract_recipients,
    _extract_guarantees,
)
from preflight.auth.audit import (
    SIEMForwarder,
    to_cef,
    to_syslog,
    AuditEntry,
    AuditEventType,
    AuditAction,
)
from preflight.db.models import (
    BoardDecision,
    BoardOverride,
    Clarification,
    PersonaVersion,
    Vendor,
    System,
    SystemRelationship,
    ArchitectureDebt,
    Retrospective,
    PersonaCalibration,
    KnowledgeSource,
    KnowledgeChunkModel,
    Citation,
    Condition,
)
from preflight.integrations.base import (
    IntegrationClient,
    IntegrationResult,
    IntegrationStatus,
)
from preflight.integrations.topdesk import TOPdeskClient
from preflight.integrations.graph import GraphClient
from preflight.integrations.leanix import LeanIXClient
from datetime import datetime, timezone


class TestDeepModeParser:
    def test_parse_deep_assessment_with_perspective_id(self):
        text = """[MY_RATING]
conditional
[/MY_RATING]

[FINDINGS]
- Patient data must be encrypted
- Access restricted to clinical staff
[/FINDINGS]

[CONDITIONS]
- Implement MFA
- Audit all access
[/CONDITIONS]

[STRONGEST_OBJECTION]
No encryption at rest specified
[/STRONGEST_OBJECTION]

[HIDDEN_CONCERN]
Vendor compliance uncertain
[/HIDDEN_CONCERN]

[MY_AUTHORITY]
VETO
[/MY_AUTHORITY]
"""
        result = parse_deep_assessment(text, "security")
        assert result.perspective_id == "security"
        assert result.rating == "conditional"
        assert len(result.findings) >= 2
        assert "MFA" in " ".join(result.conditions)
        assert result.strongest_objection == "No encryption at rest specified"
        assert result.hidden_concern == "Vendor compliance uncertain"
        assert result.authority == "VETO"

    def test_parse_deep_assessment_no_authority(self):
        text = """[MY_RATING]
approve
[/MY_RATING]

[FINDINGS]
- Good architecture
- Clean separation of concerns
[/FINDINGS]
"""
        result = parse_deep_assessment(text, "business")
        assert result.rating == "approve"
        assert result.authority is None

    def test_parse_deep_assessment_escalation_authority(self):
        text = """[MY_RATING]
concern
[/MY_RATING]

[MY_AUTHORITY]
ESCALATION
[/MY_AUTHORITY]
"""
        result = parse_deep_assessment(text, "risk")
        assert result.authority == "ESCALATION"

    def test_parse_deep_assessment_independent_authority(self):
        text = """[MY_RATING]
block
[/MY_RATING]

[MY_AUTHORITY]
INDEPENDENT
[/MY_AUTHORITY]
"""
        result = parse_deep_assessment(text, "fg-dpo")
        assert result.rating == "block"
        assert result.authority == "INDEPENDENT"

    def test_parse_deep_requires_two_args(self):
        try:
            parse_deep_assessment("text")
            assert False, "Should require perspective_id"
        except TypeError:
            pass


class TestVerwerkingsRegisterExtraction:
    PRIVE_FIN = [
        {
            "perspective_id": "data",
            "name": "Aisha",
            "findings": [
                {"finding": "BSN and medische gegevens must be encrypted at rest"},
                {"finding": "Access to patiëntdata requires MFA"},
            ],
        },
        {
            "perspective_id": "fg-dpo",
            "name": "FG/DPO",
            "findings": [
                {"finding": "AVG Artikel 6 lid 1 grondslag required for processing"},
                {"finding": "Pseudonimisatie of patiëntgegevens where possible"},
                {"finding": "Dataminimalisatie applies"},
            ],
        },
        {
            "perspective_id": "security",
            "name": "Victor",
            "findings": [
                {"finding": "Encryption required in transit and at rest"},
                {"finding": "RBAC access control for all zorggegevens"},
                {"finding": "Audit logging per NEN 7513 mandatory"},
            ],
        },
        {
            "perspective_id": "integration",
            "name": "Lena",
            "findings": [
                {"finding": "Third party leverancier integration needs DPA"},
                {"finding": "Zorgverzekeraar receives summary data"},
            ],
        },
    ]

    def test_extract_data_categories_from_findings(self):
        cats = _extract_data_categories(self.PRIVE_FIN)
        assert "BSN" in cats
        assert "medische gegevens" in cats

    def test_extract_data_categories_defaults(self):
        cats = _extract_data_categories([])
        assert "BSN" in cats
        assert "medische gegevens" in cats

    def test_extract_data_subjects(self):
        subjects = _extract_data_subjects(self.PRIVE_FIN)
        assert "Patiënten" in subjects

    def test_extract_legal_basis(self):
        basis = _extract_legal_basis(self.PRIVE_FIN)
        assert "grondslag" in basis.lower() or "AVG" in basis

    def test_extract_recipients(self):
        recipients = _extract_recipients(self.PRIVE_FIN)
        assert (
            "Leveranciers" in recipients
            or "Zorgverzekeraars" in recipients
            or len(recipients) > 0
        )

    def test_extract_guarantees(self):
        guarantees = _extract_guarantees(self.PRIVE_FIN)
        assert any("Encrypti" in g for g in guarantees)

    def test_verwerkingsregister_with_persona_findings(self):
        result = generate_verwerkingsregister_draft(
            proposal_name="Digital Pathology",
            processing_description="Processing patient data",
            persona_findings=self.PRIVE_FIN,
        )
        assert result["status"] == "CONCEPT — FG-bepaling vereist"
        cats = result["entry"]["categorie_persoonsgegevens"]
        assert "BSN" in cats
        guarantees = result["entry"]["datenschutz_garanties"]
        assert any("Encrypti" in g for g in guarantees)


class TestORMModels:
    def test_board_decision_model(self):
        bd = BoardDecision(
            assessment_id="test-assess-1",
            decision="conditional",
            decided_by="user-1",
            items=[{"finding_id": "f1", "decision": "accept", "reason": "Mitigated"}],
            notes="Board reviewed",
        )
        assert bd.decision == "conditional"
        assert bd.items[0]["decision"] == "accept"

    def test_board_override_model(self):
        bo = BoardOverride(
            decision_id="dec-1",
            finding_id="find-1",
            original_rating="block",
            override_decision="conditional",
            override_reason="Risk mitigated by compensating controls",
            overridden_by="user-2",
        )
        assert bo.original_rating == "block"
        assert bo.override_decision == "conditional"
        assert bo.decision_id == "dec-1"
        assert bo.finding_id == "find-1"

    def test_clarification_model(self):
        cl = Clarification(
            request_id="req-1",
            persona_name="Victor",
            persona_role="Security Architecture",
            question="Which encryption standard is required?",
        )
        assert cl.persona_name == "Victor"
        assert cl.answered is None or cl.answered is False

    def test_persona_version_model(self):
        pv = PersonaVersion(
            version="1.0.0",
            date=datetime.now(timezone.utc),
            persona_count=22,
            definition_hash="abc123",
        )
        assert pv.version == "1.0.0"
        assert pv.persona_count == 22

    def test_vendor_model(self):
        v = Vendor(
            name="Epic Systems",
            nen7510_status="certified",
            dpa_in_place=True,
        )
        assert v.name == "Epic Systems"
        assert v.nen7510_status == "certified"

    def test_system_model(self):
        s = System(
            name="Cloverleaf",
            type="ApplicationComponent",
            layer="Application",
            lifecycle_status="production",
            biv_b=3,
            biv_i=3,
        )
        assert s.name == "Cloverleaf"
        assert s.lifecycle_status == "production"

    def test_retrospective_model(self):
        r = Retrospective(
            assessment_id="assess-1",
            scheduled_date=datetime.now(timezone.utc),
            status="SCHEDULED",
        )
        assert r.status == "SCHEDULED"

    def test_persona_calibration_model(self):
        pc = PersonaCalibration(
            persona_name="Victor",
            perspective_id="security",
            period_start=datetime(2025, 1, 1),
            period_end=datetime(2025, 6, 30),
            total_assessments=42,
            block_count=8,
        )
        assert pc.persona_name == "Victor"
        assert pc.total_assessments == 42

    def test_knowledge_source_model(self):
        ks = KnowledgeSource(
            source_id="nen7510-12.4.1",
            title="NEN 7510 Section 12.4.1",
            source_type="regulation",
            content="All patient data access must be logged...",
            chunk_text="All patient data access must be logged",
            classification="internal",
        )
        assert ks.source_id == "nen7510-12.4.1"
        assert ks.classification == "internal"

    def test_citation_model(self):
        c = Citation(
            assessment_id="assess-1",
            source_type="KNOWLEDGE",
            source_id="nen7510-12.4.1",
        )
        assert c.source_type == "KNOWLEDGE"

    def test_architecture_debt_model(self):
        ad = ArchitectureDebt(
            debt_type="security",
            description="Missing encryption at rest",
            severity="high",
            status="open",
        )
        assert ad.severity == "high"
        assert ad.status == "open"

    def test_condition_lifecycle(self):
        c = Condition(
            assessment_id="assess-1",
            condition_text="Implement MFA",
            source_persona="Victor",
            status="OPEN",
        )
        assert c.status == "OPEN"
        assert c.can_transition("IN_PROGRESS")
        assert c.can_transition("WAIVED")
        assert not c.can_transition("MET")


class TestSIEMForwarder:
    def test_create_from_env_none_when_no_env(self):
        import os

        os.environ.pop("SIEM_TRANSPORT", None)
        result = __import__(
            "preflight.auth.audit", fromlist=["create_siem_forwarder_from_env"]
        ).create_siem_forwarder_from_env()
        assert result is None

    def test_siem_forwarder_creation(self):
        sf = SIEMForwarder(transport="udp", host="siem.local", port=514)
        assert sf.transport == "udp"
        assert sf.host == "siem.local"
        assert sf.port == 514

    def test_siem_forwarder_https(self):
        sf = SIEMForwarder(
            transport="https",
            https_url="https://siem.example.com/api/events",
            https_headers={"Authorization": "Bearer token123"},
        )
        assert sf.transport == "https"
        assert sf.https_url == "https://siem.example.com/api/events"

    def test_cef_format(self):
        entry = AuditEntry(
            timestamp=datetime.now(timezone.utc),
            event_type=AuditEventType.AUTHZ,
            action=AuditAction.ACCESSED,
            actor_id="user-1",
            actor_role="architect",
            resource_type="assessment",
            resource_id="assess-1",
            classification="internal",
        )
        cef = to_cef(entry)
        assert cef.startswith("CEF:0|EA-Council|Preflight|0.2.0|")
        assert "authz" in cef
        assert "suser=user-1" in cef

    def test_syslog_format(self):
        entry = AuditEntry(
            timestamp=datetime.now(timezone.utc),
            event_type=AuditEventType.VETO,
            action=AuditAction.VETO_ISSUED,
            actor_id="user-1",
            actor_role="security-architect",
            resource_type="assessment",
            resource_id="assess-1",
            classification="confidential",
        )
        line = to_syslog(entry)
        assert line.startswith("<")
        assert "preflight:" in line
        assert "CEF:0" in line


class TestIntegrationClients:
    def test_topdesk_client_create(self):
        client = TOPdeskClient(base_url="https://topdesk.example.com", api_key="key")
        assert client.source == "topdesk"
        assert client.base_url == "https://topdesk.example.com"

    def test_topdesk_normalize(self):
        client = TOPdeskClient(base_url="https://topdesk.example.com")
        raw = {
            "id": "app-1",
            "name": "Epic",
            "assetType": "Clinical",
            "status": "production",
        }
        result = client.normalize(raw)
        assert result["name"] == "Epic"
        assert result["type"] == "Clinical"

    def test_graph_client_create(self):
        client = GraphClient(base_url="https://graph.microsoft.com/v1.0")
        assert client.source == "graph"

    def test_graph_normalize(self):
        client = GraphClient()
        raw = {
            "id": "doc-1",
            "name": "NEN 7510 Policy.pdf",
            "file": {"mimeType": "application/pdf"},
            "webUrl": "https://sharepoint.local/doc1",
        }
        result = client.normalize(raw)
        assert result["name"] == "NEN 7510 Policy.pdf"

    def test_leanix_client_create(self):
        client = LeanIXClient(base_url="https://eu.leanix.net/services/pathfinder/v1")
        assert client.source == "leanix"

    def test_leanix_normalize(self):
        client = LeanIXClient()
        raw = {
            "id": "fs-1",
            "displayName": "Cloverleaf",
            "type": "Application",
            "lifecycle": {"phase": "production"},
            "businessCriticality": "high",
        }
        result = client.normalize(raw)
        assert result["name"] == "Cloverleaf"
        assert result["status"] == "production"

    def test_base_client_health_raises(self):
        client = IntegrationClient(base_url="https://example.com")
        try:
            import asyncio

            asyncio.get_event_loop().run_until_complete(client.health())
            assert False, "Should raise NotImplementedError"
        except NotImplementedError:
            pass

    def test_integration_result_ok(self):
        r = IntegrationResult(status=IntegrationStatus.SUCCESS, source="test")
        assert r.ok is True

        r2 = IntegrationResult(status=IntegrationStatus.FAILED, source="test")
        assert r2.ok is False


class TestKnowledgeChunkModel:
    def test_knowledge_chunk_model_fields(self):
        kc = KnowledgeChunkModel(
            id="test-chunk-1",
            source_id="nen7510-12.4.1",
            source_type="regulation",
            title="NEN 7510 Section 12.4.1",
            content="All patient data access must be logged",
            chunk_text="All patient data access must be logged",
            enriched_keyword="ZIRA: principe-6 | REGS: NEN 7510",
            enriched_semantic="ZiRA principle: Veilig\nRegulation: NEN 7510",
            context_prefix="Section 12.4.1: Logging requirements",
            language="nl",
            classification="internal",
        )
        assert kc.source_id == "nen7510-12.4.1"
        assert kc.enriched_keyword.startswith("ZIRA:")
        assert "ZiRA principle:" in kc.enriched_semantic
        assert kc.context_prefix == "Section 12.4.1: Logging requirements"
        assert kc.language == "nl"

    def test_knowledge_chunk_model_defaults(self):
        kc = KnowledgeChunkModel(
            id="test-chunk-2",
            source_id="avg-art35",
            source_type="regulation",
            title="AVG Artikel 35",
            content="Data subject rights",
            chunk_text="Data subject rights",
            enriched_keyword="",
            enriched_semantic="",
            language="nl",
            content_type="generic",
            classification="internal",
        )
        assert kc.enriched_keyword == ""
        assert kc.enriched_semantic == ""
        assert kc.content_type == "generic"
        assert kc.classification == "internal"

    def test_knowledge_chunk_model_tablename(self):
        assert KnowledgeChunkModel.__tablename__ == "knowledge_chunk"
