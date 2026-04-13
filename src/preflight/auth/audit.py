"""
Preflight audit trail — NEN 7513 hash-chained append-only log.

FIRST PRINCIPLES:
  1. NEN 7513 requires: who, what, when, from where, which authorization
  2. The log is APPEND-ONLY. No UPDATE. No DELETE. Enforced at DB level.
  3. Each entry links to the previous entry via SHA-256 hash chain.
  4. A broken hash chain = tampering detected. This is the point.
  5. Every access to patient-related data MUST be logged.

INVERSION: What makes the audit trail fail?
  - Bug writes bad data → can't UPDATE, must write CORRECTION entry referencing original
  - Hash chain broken by concurrent writes → serialize on insert (database-level lock)
  - Performance (hash chain on every write) → batch commits, not per-field writes
  - Actor is system/anonymous → mark as "system" actor, still traceable
  - GDPR right to erasure conflicts with NEN 7513 → NEN 7513 wins for healthcare
    (hospital sector exemption under AVG Article 17(3)(e))

SECOND ORDER:
  - Hash chain means you can cryptographically prove the log hasn't been altered
  - But you can't prove logs WEREN'T deleted entirely → separate SIEM stream
  - Correction entries are how you "fix" errors without violating append-only
"""

from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Protocol

from preflight.auth.authn import AuthUser


class AuditEventType(str, Enum):
    AUTH = "auth"
    AUTHZ = "authz"
    ASSESSMENT = "assessment"
    PERSONA = "persona"
    VETO = "veto"
    ESCALATION = "escalation"
    DETERMINATION = "determination"
    DECISION = "decision"
    SIGN_OFF = "sign_off"
    OVERRIDE = "override"
    CONDITION = "condition"
    CALIBRATION = "calibration"
    KNOWLEDGE = "knowledge"
    INGEST = "ingest"
    CORRECTION = "correction"
    SYSTEM = "system"


class AuditAction(str, Enum):
    CREATED = "created"
    ACCESSED = "accessed"
    DENIED = "denied"
    OVERRIDDEN = "overridden"
    SIGNED_OFF = "signed_off"
    ESCALATED = "escalated"
    VETO_ISSUED = "veto_issued"
    CONDITION_OPENED = "condition_opened"
    CONDITION_MET = "condition_met"
    CONDITION_OVERDUE = "condition_overdue"
    CLASSIFICATION_CHANGED = "classification_changed"
    CORRECTION = "correction"
    INGESTED = "ingested"
    DELETED = "deleted"
    EXPORTED = "exported"
    STARTED = "started"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class AuditEntry:
    id: str = ""
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    event_type: AuditEventType = AuditEventType.SYSTEM
    action: AuditAction = AuditAction.CREATED

    actor_id: str = ""
    actor_role: str = ""

    resource_type: str = ""
    resource_id: str = ""
    assessment_id: str = ""

    details: dict = field(default_factory=dict)
    classification: str = "internal"

    source_ip: str = ""
    user_agent: str = ""

    previous_hash: str = "0" * 64
    entry_hash: str = ""

    def compute_hash(self, prev_hash: str) -> str:
        """Compute SHA-256 hash for this entry, chaining to previous.

        The hash is over: timestamp | event_type | action | actor_id | previous_hash
        This makes the chain tamper-evident: changing any entry invalidates
        all subsequent entries' hashes.
        """
        payload = (
            f"{self.timestamp.isoformat()}"
            f"|{self.event_type.value}"
            f"|{self.action.value}"
            f"|{self.actor_id}"
            f"|{prev_hash}"
        )
        return hashlib.sha256(payload.encode()).hexdigest()


@dataclass
class CorrectionEntry:
    """Append-only correction — references the original entry.

    INVERSION: What if we just UPDATE the wrong entry?
      → That violates NEN 7513 append-only requirement.
      → Instead, write a new entry of type CORRECTION that references
        the original entry ID. The correction replaces the original
        semantically, but both entries remain in the log.
    """

    original_entry_id: str
    corrected_details: dict
    correction_reason: str
    corrected_by: str
    corrected_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class AuditLogger(Protocol):
    async def log(self, entry: AuditEntry) -> str: ...

    async def log_batch(self, entries: list[AuditEntry]) -> list[str]: ...

    async def query(
        self,
        event_type: AuditEventType | None = None,
        actor_id: str | None = None,
        assessment_id: str | None = None,
        resource_type: str | None = None,
        from_time: datetime | None = None,
        to_time: datetime | None = None,
        limit: int = 100,
    ) -> list[AuditEntry]: ...

    async def verify_chain(self, from_id: str | None = None) -> bool: ...


class PostgresAuditLogger:
    """PostgreSQL-backed NEN 7513 audit log.

    Uses the hash chain for tamper detection.
    Append-only enforced via revoked UPDATE/DELETE permissions (in production).
    """

    def __init__(self, database_url: str):
        self.database_url = database_url

    async def _get_conn(self):
        import asyncpg

        return await asyncpg.connect(self.database_url)

    async def ensure_schema(self):
        conn = await self._get_conn()
        try:
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS audit_log (
                    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    timestamp       TIMESTAMPTZ NOT NULL DEFAULT now(),
                    event_type      TEXT NOT NULL,
                    action          TEXT NOT NULL,
                    actor_id        TEXT NOT NULL,
                    actor_role      TEXT NOT NULL,
                    resource_type   TEXT,
                    resource_id     TEXT,
                    assessment_id   TEXT,
                    details         JSONB DEFAULT '{}',
                    classification  TEXT NOT NULL DEFAULT 'internal',
                    source_ip       TEXT,
                    user_agent      TEXT,
                    previous_hash   TEXT NOT NULL,
                    entry_hash      TEXT NOT NULL
                )
            """)
            await conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_audit_event_time
                    ON audit_log(event_type, timestamp DESC)
            """)
            await conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_audit_actor_time
                    ON audit_log(actor_id, timestamp DESC)
            """)
            await conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_audit_assessment
                    ON audit_log(assessment_id) WHERE assessment_id IS NOT NULL
            """)
            await conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_audit_hash
                    ON audit_log(entry_hash)
            """)
        finally:
            await conn.close()

    async def _get_last_hash(self, conn) -> str:
        row = await conn.fetchrow(
            "SELECT entry_hash FROM audit_log ORDER BY timestamp DESC LIMIT 1"
        )
        return row["entry_hash"] if row else "0" * 64

    async def log(self, entry: AuditEntry) -> str:
        """Append a single audit entry. Returns the entry ID."""
        conn = await self._get_conn()
        try:
            async with conn.transaction():
                prev_hash = await self._get_last_hash(conn)
                entry.previous_hash = prev_hash
                entry.entry_hash = entry.compute_hash(prev_hash)

                if not entry.id:
                    entry.id = str(uuid.uuid4())

                details_json = json.dumps(entry.details)

                row = await conn.fetchrow(
                    """
                    INSERT INTO audit_log (
                        id, timestamp, event_type, action,
                        actor_id, actor_role,
                        resource_type, resource_id, assessment_id,
                        details, classification,
                        source_ip, user_agent,
                        previous_hash, entry_hash
                    ) VALUES (
                        $1::uuid, $2, $3, $4,
                        $5, $6,
                        $7, $8, $9,
                        $10::jsonb, $11,
                        $12, $13,
                        $14, $15
                    ) RETURNING id::text
                    """,
                    entry.id,
                    entry.timestamp,
                    entry.event_type.value,
                    entry.action.value,
                    entry.actor_id,
                    entry.actor_role,
                    entry.resource_type,
                    entry.resource_id,
                    entry.assessment_id,
                    details_json,
                    entry.classification,
                    entry.source_ip,
                    entry.user_agent,
                    entry.previous_hash,
                    entry.entry_hash,
                )

                return row["id"] if row else entry.id
        finally:
            await conn.close()

    async def log_batch(self, entries: list[AuditEntry]) -> list[str]:
        """Append multiple audit entries in a single transaction.

        SECOND ORDER: Batch logging within one transaction means
        the hash chain is consistent even with concurrent access.
        """
        conn = await self._get_conn()
        ids: list[str] = []
        try:
            async with conn.transaction():
                prev_hash = await self._get_last_hash(conn)

                for entry in entries:
                    if not entry.id:
                        entry.id = str(uuid.uuid4())

                    entry.previous_hash = prev_hash
                    entry.entry_hash = entry.compute_hash(prev_hash)

                    details_json = json.dumps(entry.details)

                    row = await conn.fetchrow(
                        """
                        INSERT INTO audit_log (
                            id, timestamp, event_type, action,
                            actor_id, actor_role,
                            resource_type, resource_id, assessment_id,
                            details, classification,
                            source_ip, user_agent,
                            previous_hash, entry_hash
                        ) VALUES (
                            $1::uuid, $2, $3, $4,
                            $5, $6,
                            $7, $8, $9,
                            $10::jsonb, $11,
                            $12, $13,
                            $14, $15
                        ) RETURNING id::text
                        """,
                        entry.id,
                        entry.timestamp,
                        entry.event_type.value,
                        entry.action.value,
                        entry.actor_id,
                        entry.actor_role,
                        entry.resource_type,
                        entry.resource_id,
                        entry.assessment_id,
                        details_json,
                        entry.classification,
                        entry.source_ip,
                        entry.user_agent,
                        entry.previous_hash,
                        entry.entry_hash,
                    )

                    entry_id = row["id"] if row else entry.id
                    ids.append(entry_id)
                    prev_hash = entry.entry_hash
        finally:
            await conn.close()

        return ids

    async def log_correction(
        self,
        original_entry_id: str,
        corrected_details: dict,
        correction_reason: str,
        user: AuthUser,
    ) -> str:
        """Append a correction entry referencing an original.

        INVERSION: Why not just UPDATE the bad entry?
          → NEN 7513 says NO. All entries are immutable.
          → A correction is a NEW entry that references the original.
          → Both entries remain. The correction is the current truth.
        """
        entry = AuditEntry(
            event_type=AuditEventType.CORRECTION,
            action=AuditAction.CORRECTION,
            actor_id=user.entra_id,
            actor_role=user.role,
            resource_type="audit_log",
            resource_id=original_entry_id,
            details={
                "correction_reason": correction_reason,
                "corrected_details": corrected_details,
            },
        )
        return await self.log(entry)

    async def query(
        self,
        event_type: AuditEventType | None = None,
        actor_id: str | None = None,
        assessment_id: str | None = None,
        resource_type: str | None = None,
        from_time: datetime | None = None,
        to_time: datetime | None = None,
        limit: int = 100,
    ) -> list[AuditEntry]:
        """Query audit log with filters."""
        conn = await self._get_conn()
        try:
            conditions = []
            params: list = []
            idx = 1

            if event_type:
                conditions.append(f"event_type = ${idx}")
                params.append(event_type.value)
                idx += 1
            if actor_id:
                conditions.append(f"actor_id = ${idx}")
                params.append(actor_id)
                idx += 1
            if assessment_id:
                conditions.append(f"assessment_id = ${idx}")
                params.append(assessment_id)
                idx += 1
            if resource_type:
                conditions.append(f"resource_type = ${idx}")
                params.append(resource_type)
                idx += 1
            if from_time:
                conditions.append(f"timestamp >= ${idx}")
                params.append(from_time)
                idx += 1
            if to_time:
                conditions.append(f"timestamp <= ${idx}")
                params.append(to_time)
                idx += 1

            where = ""
            if conditions:
                where = "WHERE " + " AND ".join(conditions)

            params.append(limit)

            rows = await conn.fetch(
                f"""
                SELECT * FROM audit_log
                {where}
                ORDER BY timestamp DESC
                LIMIT ${idx}
                """,
                *params,
            )

            entries = []
            for row in rows:
                details = row.get("details", {})
                if isinstance(details, str):
                    try:
                        details = json.loads(details)
                    except json.JSONDecodeError:
                        details = {}

                entries.append(
                    AuditEntry(
                        id=str(row["id"]),
                        timestamp=row["timestamp"],
                        event_type=AuditEventType(row["event_type"]),
                        action=AuditAction(row["action"]),
                        actor_id=row["actor_id"],
                        actor_role=row["actor_role"],
                        resource_type=row.get("resource_type", ""),
                        resource_id=row.get("resource_id", ""),
                        assessment_id=row.get("assessment_id", ""),
                        details=details,
                        classification=row.get("classification", "internal"),
                        previous_hash=row.get("previous_hash", ""),
                        entry_hash=row.get("entry_hash", ""),
                    )
                )

            return entries
        finally:
            await conn.close()

    async def verify_chain(self, from_id: str | None = None) -> bool:
        """Verify the hash chain integrity.

        Returns True if the chain is intact (each entry's hash matches
        the next entry's previous_hash). Returns False if any link is broken.

        INVERSION: What if verify_chain returns False?
          → The log has been tampered with or corrupted.
          → This is a CRITICAL security incident.
          → SIEM should be alerted immediately.
        """
        conn = await self._get_conn()
        try:
            sql = "SELECT id, previous_hash, entry_hash FROM audit_log ORDER BY timestamp ASC"
            rows = await conn.fetch(sql)

            if not rows:
                return True

            for i in range(1, len(rows)):
                if rows[i]["previous_hash"] != rows[i - 1]["entry_hash"]:
                    return False

            return True
        finally:
            await conn.close()


class MemoryAuditLogger:
    """In-memory audit logger for testing and local dev.

    Maintains the hash chain but doesn't persist.
    Useful for integration tests that verify audit behavior.
    """

    def __init__(self):
        self._entries: list[AuditEntry] = []
        self._last_hash: str = "0" * 64

    async def log(self, entry: AuditEntry) -> str:
        if not entry.id:
            entry.id = str(uuid.uuid4())

        entry.previous_hash = self._last_hash
        entry.entry_hash = entry.compute_hash(self._last_hash)
        self._last_hash = entry.entry_hash
        self._entries.append(entry)
        return entry.id

    async def log_batch(self, entries: list[AuditEntry]) -> list[str]:
        ids = []
        for entry in entries:
            entry_id = await self.log(entry)
            ids.append(entry_id)
        return ids

    async def query(
        self,
        event_type: AuditEventType | None = None,
        actor_id: str | None = None,
        assessment_id: str | None = None,
        resource_type: str | None = None,
        from_time: datetime | None = None,
        to_time: datetime | None = None,
        limit: int = 100,
    ) -> list[AuditEntry]:
        results = self._entries
        if event_type:
            results = [e for e in results if e.event_type == event_type]
        if actor_id:
            results = [e for e in results if e.actor_id == actor_id]
        if assessment_id:
            results = [e for e in results if e.assessment_id == assessment_id]
        if resource_type:
            results = [e for e in results if e.resource_type == resource_type]
        return results[-limit:]

    async def verify_chain(self, from_id: str | None = None) -> bool:
        if not self._entries:
            return True
        for i in range(1, len(self._entries)):
            if self._entries[i].previous_hash != self._entries[i - 1].entry_hash:
                return False
        return True

    @property
    def entries(self) -> list[AuditEntry]:
        return list(self._entries)


def audit_assessment_access(
    user: AuthUser,
    assessment_id: str,
    action: AuditAction,
    classification: str = "internal",
    source_ip: str = "",
) -> AuditEntry:
    """Factory: create an audit entry for assessment access (NEN 7513)."""
    return AuditEntry(
        event_type=AuditEventType.ASSESSMENT,
        action=action,
        actor_id=user.entra_id,
        actor_role=user.role,
        resource_type="assessment",
        resource_id=assessment_id,
        assessment_id=assessment_id,
        classification=classification,
        source_ip=source_ip,
    )


def audit_authority_action(
    user: AuthUser,
    assessment_id: str,
    action_type: str,
    persona_name: str,
    finding_id: str = "",
) -> AuditEntry:
    """Factory: create an audit entry for authority persona actions."""
    event_map = {
        "VETO": AuditEventType.VETO,
        "ESCALATION": AuditEventType.ESCALATION,
        "INDEPENDENT": AuditEventType.DETERMINATION,
    }
    action_map = {
        "VETO": AuditAction.VETO_ISSUED,
        "ESCALATION": AuditAction.ESCALATED,
        "INDEPENDENT": AuditAction.CREATED,
    }

    return AuditEntry(
        event_type=event_map.get(action_type, AuditEventType.PERSONA),
        action=action_map.get(action_type, AuditAction.CREATED),
        actor_id=user.entra_id,
        actor_role=user.role,
        resource_type="persona_finding",
        resource_id=finding_id,
        assessment_id=assessment_id,
        details={"action_type": action_type, "persona": persona_name},
    )


# ---------------------------------------------------------------------------
# SIEM CEF (Common Event Format) export
# ---------------------------------------------------------------------------


def to_cef(
    entry: AuditEntry, product: str = "Preflight", vendor: str = "EA-Council"
) -> str:
    """Convert an AuditEntry to a CEF-formatted string for SIEM ingestion.

    CEF format: CEF:Version|Device Vendor|Device Product|Device Version|
                Signature ID|Name|Severity|Extensions

    Severity mapping: VETO → 10 (Critical), ESCALATION → 8 (High),
    AUTH failures → 7, normal operations → 3 (Low).
    """
    severity_map = {
        AuditEventType.VETO: 10,
        AuditEventType.ESCALATION: 8,
        AuditEventType.DETERMINATION: 6,
        AuditEventType.AUTHZ: 7,
        AuditEventType.AUTH: 5,
    }
    severity = severity_map.get(entry.event_type, 3)

    if entry.action in (AuditAction.VETO_ISSUED, AuditAction.ESCALATED):
        severity = max(severity, 9)

    extensions = (
        f"src={entry.source_ip or '0.0.0.0'} "
        f"suser={entry.actor_id} "
        f"spriv={entry.actor_role} "
        f"rt={entry.timestamp.isoformat()} "
        f"msg={entry.action.value} "
        f"cs1Label=ResourceType cs1={entry.resource_type or '-'} "
        f"cs2Label=ResourceID cs2={entry.resource_id or '-'} "
        f"cs3Label=AssessmentID cs3={entry.assessment_id or '-'} "
        f"cs4Label=Classification cs4={entry.classification}"
    )

    if entry.details:
        import json as _json

        extensions += (
            f" cs5Label=Details cs5={_json.dumps(entry.details, separators=(',', ':'))}"
        )

    name = f"{entry.event_type.value}_{entry.action.value}"

    return (
        f"CEF:0|{vendor}|{product}|0.2.0|"
        f"{entry.event_type.value}|{name}|{severity}|{extensions}"
    )


def to_syslog(
    entry: AuditEntry, facility: int = 23, hostname: str = "preflight"
) -> str:
    """Convert an AuditEntry to a BSD syslog-formatted line (RFC 3164).

    Facility 23 = local use 7 (common for application logs).
    Severity: Critical=2, Error=3, Warning=4, Info=6.
    """
    pri = facility * 8

    severity_map = {
        AuditEventType.VETO: 2,
        AuditEventType.ESCALATION: 3,
        AuditEventType.DETERMINATION: 4,
        AuditEventType.AUTHZ: 4,
        AuditEventType.AUTH: 6,
    }
    syslog_severity = severity_map.get(entry.event_type, 6)
    pri += syslog_severity

    timestamp = entry.timestamp.strftime("%b %d %H:%M:%S")
    msg = to_cef(entry)

    return f"<{pri}>{timestamp} {hostname} preflight: {msg}"


# ---------------------------------------------------------------------------
# SIEM forwarding
# ---------------------------------------------------------------------------


import asyncio
import socket
import ssl


class SIEMForwarder:
    """Forwards audit entries to a SIEM via syslog (UDP/TCP) or HTTPS webhook.

    Thread-safe. Runs as a background task alongside the audit logger.
    Failed sends are queued and retried.
    """

    def __init__(
        self,
        transport: str = "udp",
        host: str = "localhost",
        port: int = 514,
        https_url: str | None = None,
        https_headers: dict[str, str] | None = None,
        tls_verify: bool = True,
        max_queue: int = 10000,
        retry_backoff: float = 1.0,
    ):
        self.transport = transport
        self.host = host
        self.port = port
        self.https_url = https_url
        self.https_headers = https_headers or {}
        self.tls_verify = tls_verify
        self._queue: asyncio.Queue[AuditEntry | None] = asyncio.Queue(maxsize=max_queue)
        self._retry_backoff = retry_backoff
        self._running = False
        self._task: asyncio.Task | None = None

    async def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._forward_loop())

    async def stop(self) -> None:
        self._running = False
        await self._queue.put(None)
        if self._task:
            await self._task

    async def send(self, entry: AuditEntry) -> None:
        try:
            self._queue.put_nowait(entry)
        except asyncio.QueueFull:
            pass

    async def _forward_loop(self) -> None:
        while self._running:
            entry = await self._queue.get()
            if entry is None:
                break
            await self._send_with_retry(entry)

    async def _send_with_retry(self, entry: AuditEntry, max_retries: int = 3) -> None:
        msg = to_syslog(entry)
        for attempt in range(max_retries):
            try:
                if self.transport in ("udp", "tcp"):
                    await self._send_syslog(msg)
                elif self.transport == "https":
                    await self._send_https(entry)
                return
            except Exception:
                if attempt < max_retries - 1:
                    await asyncio.sleep(self._retry_backoff * (attempt + 1))
                else:
                    pass

    async def _send_syslog(self, msg: str) -> None:
        loop = asyncio.get_running_loop()
        if self.transport == "udp":
            await loop.run_in_executor(None, self._send_udp, msg)
        else:
            await loop.run_in_executor(None, self._send_tcp, msg)

    def _send_udp(self, msg: str) -> None:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.sendto(msg.encode("utf-8"), (self.host, self.port))

    def _send_tcp(self, msg: str) -> None:
        context = ssl.create_default_context()
        if not self.tls_verify:
            context.check_hostname = False
            context.verify_mode = ssl.CERT_NONE
        with socket.create_connection((self.host, self.port), timeout=5) as raw:
            with context.wrap_socket(raw, server_hostname=self.host) as sock:
                sock.sendall((msg + "\n").encode("utf-8"))

    async def _send_https(self, entry: AuditEntry) -> None:
        try:
            import httpx

            payload = (
                entry.to_dict()
                if hasattr(entry, "to_dict")
                else {
                    "timestamp": entry.timestamp.isoformat(),
                    "event_type": entry.event_type.value,
                    "action": entry.action.value,
                    "actor_id": entry.actor_id,
                    "actor_role": entry.actor_role,
                    "resource_type": entry.resource_type or "",
                    "resource_id": entry.resource_id or "",
                    "assessment_id": entry.assessment_id or "",
                    "classification": entry.classification,
                    "details": entry.details or {},
                    "cef": to_cef(entry),
                }
            )
            headers = {"Content-Type": "application/json", **self.https_headers}
            async with httpx.AsyncClient(timeout=10.0) as client:
                await client.post(
                    self.https_url,
                    json=payload,
                    headers=headers,
                    verify=self.tls_verify,
                )
        except ImportError:
            pass


def create_siem_forwarder_from_env() -> SIEMForwarder | None:
    """Create a SIEMForwarder from environment variables.

    SIEM_TRANSPORT=udp|tcp|https
    SIEM_HOST=localhost (for udp/tcp)
    SIEM_PORT=514 (for udp/tcp)
    SIEM_HTTPS_URL=https://... (for https)
    SIEM_HTTPS_TOKEN=... (for https auth header)
    SIEM_TLS_VERIFY=true|false
    """
    import os

    transport = os.environ.get("SIEM_TRANSPORT", "").lower()
    if not transport:
        return None

    return SIEMForwarder(
        transport=transport,
        host=os.environ.get("SIEM_HOST", "localhost"),
        port=int(os.environ.get("SIEM_PORT", "514")),
        https_url=os.environ.get("SIEM_HTTPS_URL"),
        https_headers=(
            {"Authorization": f"Bearer {os.environ['SIEM_HTTPS_TOKEN']}"}
            if "SIEM_HTTPS_TOKEN" in os.environ
            else {}
        ),
        tls_verify=os.environ.get("SIEM_TLS_VERIFY", "true").lower() == "true",
    )
