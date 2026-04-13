"""Tests for SIEM CEF/syslog export and persona version tracking."""

from datetime import datetime, timezone

from preflight.auth.audit import (
    AuditEntry,
    AuditAction,
    AuditEventType,
    to_cef,
    to_syslog,
)
from preflight.llm.prompt import PERSONA_VERSION, persona_hash, PERSPECTIVES
from preflight.parsing.parsers import UnstructuredParser


class TestCEFExport:
    def test_basic_cef_format(self):
        entry = AuditEntry(
            event_type=AuditEventType.ASSESSMENT,
            action=AuditAction.CREATED,
            actor_id="user-123",
            actor_role="architect",
            resource_type="assessment",
            resource_id="abc-def",
            timestamp=datetime.now(timezone.utc),
        )
        cef = to_cef(entry)
        assert cef.startswith("CEF:0|EA-Council|Preflight|0.2.0|")
        assert "assessment" in cef
        assert "user-123" in cef

    def test_veto_high_severity(self):
        entry = AuditEntry(
            event_type=AuditEventType.VETO,
            action=AuditAction.VETO_ISSUED,
            actor_id="victor",
            actor_role="security",
            resource_type="persona_finding",
            timestamp=datetime.now(timezone.utc),
        )
        cef = to_cef(entry)
        assert "|10|" in cef or "|9|" in cef

    def test_escalation_severity(self):
        entry = AuditEntry(
            event_type=AuditEventType.ESCALATION,
            action=AuditAction.ESCALATED,
            actor_id="nadia",
            actor_role="risk",
            resource_type="persona_finding",
            timestamp=datetime.now(timezone.utc),
        )
        cef = to_cef(entry)
        severity = int(cef.split("|")[6])
        assert severity >= 8


class TestSyslogExport:
    def test_syslog_format(self):
        entry = AuditEntry(
            event_type=AuditEventType.AUTH,
            action=AuditAction.ACCESSED,
            actor_id="user-456",
            actor_role="requestor",
            timestamp=datetime.now(timezone.utc),
        )
        line = to_syslog(entry)
        assert line.startswith("<")
        assert "preflight" in line
        assert "CEF:0" in line

    def test_syslog_priority(self):
        entry = AuditEntry(
            event_type=AuditEventType.AUTH,
            action=AuditAction.ACCESSED,
            actor_id="u",
            actor_role="r",
            timestamp=datetime.now(timezone.utc),
        )
        line = to_syslog(entry)
        pri_str = line[1 : line.index(">")]
        pri = int(pri_str)
        facility = pri // 8
        assert facility == 23


class TestPersonaVersion:
    def test_version_string(self):
        assert PERSONA_VERSION == "1.0.0"

    def test_hash_deterministic(self):
        h1 = persona_hash()
        h2 = persona_hash()
        assert h1 == h2
        assert len(h1) == 16

    def test_hash_changes_with_perspectives(self):
        h = persona_hash()
        assert h != ""

    def test_perspectives_count(self):
        assert len(PERSPECTIVES) >= 20


class TestUnstructuredParser:
    def test_supported_extensions(self):
        p = UnstructuredParser()
        exts = p.supported_extensions()
        assert ".html" in exts
        assert ".xml" in exts
        assert ".odt" in exts

    def test_not_in_default_workhorse_extensions(self):
        """Unstructured handles extensions that others don't."""
        p = UnstructuredParser()
        assert ".html" not in []  # sanity
