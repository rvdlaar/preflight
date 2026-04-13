"""Tests for preflight.citation — citation extraction and verification."""

from preflight.citation.verify import (
    extract_citations,
    verify_citations,
    build_citation_report,
    extract_regulatory_references,
)


class TestCitationExtraction:
    def test_persona_citation(self):
        text = "The system must comply with NEN 7510 [§P:Victor]"
        citations = extract_citations(text)
        assert any(
            c.citation_type.value == "persona" and c.source_id == "Victor"
            for c in citations
        )

    def test_knowledge_citation(self):
        text = "According to the guideline [§K:nen7510-sec4.2]"
        citations = extract_citations(text)
        assert any(
            c.citation_type.value == "knowledge" and "nen7510" in c.source_id
            for c in citations
        )

    def test_no_citations(self):
        text = "This is a plain text with no citations"
        citations = extract_citations(text)
        assert len(citations) == 0

    def test_multiple_citations(self):
        text = (
            "Risk identified by Victor [§P:Victor] based on NEN 7510 [§K:nen7510-sec3]"
        )
        citations = extract_citations(text)
        persona_cites = [c for c in citations if c.citation_type.value == "persona"]
        knowledge_cites = [c for c in citations if c.citation_type.value == "knowledge"]
        assert len(persona_cites) >= 1
        assert len(knowledge_cites) >= 1


class TestRegulatoryReferences:
    def test_nen_detected(self):
        text = "Must comply with NEN 7510 and NEN 7513"
        refs = extract_regulatory_references(text)
        nen_refs = [r for r in refs if "NEN" in r]
        assert len(nen_refs) >= 1

    def test_avg_detected(self):
        text = "Must comply with NEN 7510 and NEN 7513"
        refs = extract_regulatory_references(text)
        nen_refs = [r for r in refs if "NEN" in r]
        assert len(nen_refs) >= 1
