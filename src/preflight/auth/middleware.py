"""
Preflight Auth middleware — FastAPI dependency injection for AuthN + AuthZ + Audit.

Wires together:
  - AuthN: Entra ID OIDC or dev API key
  - AuthZ: RBAC + ABAC checks via Authorizer
  - Audit: NEN 7513 logging for every access

FIRST PRINCIPLE: Every API endpoint MUST go through auth.
No unauthenticated access except /health (intentional for load balancers).

INVERSION: What if auth fails mid-request?
  → 401 Unauthorized (no user) or 403 Forbidden (wrong role)
  → The assessment pipeline continues for other users
  → Audit log records the failed attempt (NEN 7513 requirement)
"""

from __future__ import annotations

import logging
from typing import Annotated

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from preflight.auth.authn import (
    AuthUser,
    AuthConfig,
    EntraIDValidator,
    DevApiKeyValidator,
    RoleMapper,
    build_token_config,
)
from preflight.auth.authz import (
    Authorizer,
    Action,
    Classification,
)
from preflight.auth.audit import (
    AuditLogger,
    AuditAction,
    MemoryAuditLogger,
    audit_assessment_access,
    SIEMForwarder,
    create_siem_forwarder_from_env,
)

logger = logging.getLogger(__name__)

_bearer_scheme = HTTPBearer(auto_error=False)

_auth_config: AuthConfig | None = None
_entra_validator: EntraIDValidator | None = None
_dev_validator: DevApiKeyValidator | None = None
_authorizer: Authorizer | None = None
_audit_logger: AuditLogger | None = None
_siem_forwarder: SIEMForwarder | None = None


def configure_auth(
    auth_config: AuthConfig | None = None,
    audit_logger: AuditLogger | None = None,
    siem_forwarder: SIEMForwarder | None = None,
):
    """Configure auth dependencies. Call once at app startup."""
    global \
        _auth_config, \
        _entra_validator, \
        _dev_validator, \
        _authorizer, \
        _audit_logger, \
        _siem_forwarder

    _auth_config = auth_config or AuthConfig.from_env()
    _authorizer = Authorizer()

    if _auth_config.dev_mode:
        logger.warning(
            "⚠ PREFLIGHT DEV MODE ACTIVE — API key authentication, NOT for production"
        )
        _dev_validator = DevApiKeyValidator()
        _entra_validator = None
    else:
        token_config = build_token_config(
            tenant_id=_auth_config.tenant_id,
            client_id=_auth_config.client_id,
        )
        role_mapper = RoleMapper(_auth_config.group_role_map)
        _entra_validator = EntraIDValidator(token_config, role_mapper)
        _dev_validator = None

    _audit_logger = audit_logger or MemoryAuditLogger()

    if siem_forwarder is None:
        siem_forwarder = create_siem_forwarder_from_env()
    _siem_forwarder = siem_forwarder


async def get_current_user(
    request: Request,
    credentials: Annotated[
        HTTPAuthorizationCredentials | None, Depends(_bearer_scheme)
    ] = None,
) -> AuthUser:
    """FastAPI dependency: extract and validate user from request.

    Phase 1: Checks Bearer token (API key in dev mode, JWT in production).
    Returns AuthUser with role, department, clearance.
    Raises 401 if no valid credentials.
    """
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = credentials.credentials

    if _auth_config and _auth_config.dev_mode and _dev_validator:
        user = _dev_validator.validate_key(token)
        if user:
            return user
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key",
        )

    if _entra_validator:
        user = await _entra_validator.validate_token(token)
        if user:
            return user

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired token",
    )


def require_role(*roles: str):
    """FastAPI dependency factory: require one of the given RBAC roles.

    Usage: @app.get("/admin", dependencies=[Depends(require_role("admin"))])
    """

    async def _check_role(user: AuthUser = Depends(get_current_user)) -> AuthUser:
        if not _authorizer:
            raise HTTPException(status_code=500, detail="Auth not configured")

        action_map = {
            "admin": Action.ADMIN_CONFIG,
            "chief-architect": Action.MANAGE_PERSONAS,
            "architect": Action.RUN_ASSESSMENT,
            "lead-architect": Action.RUN_ASSESSMENT,
            "board-chair": Action.BOARD_DECISION,
            "compliance-officer": Action.EXPORT_AUDIT,
            "fg-dpo": Action.SIGN_OFF_AUTHORITY,
            "cio": Action.VIEW_DASHBOARD,
            "requestor": Action.SUBMIT_REQUEST,
        }

        for role in roles:
            action = action_map.get(role, Action.VIEW_ASSESSMENT)
            decision = _authorizer.check_rbac(user, action)
            if decision.allowed:
                return user

        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Role '{user.role}' not authorized. Required: {', '.join(roles)}",
        )

    return _check_role


def require_action(action: Action):
    """FastAPI dependency factory: require permission for a specific action."""

    async def _check_action(user: AuthUser = Depends(get_current_user)) -> AuthUser:
        if not _authorizer:
            raise HTTPException(status_code=500, detail="Auth not configured")

        decision = _authorizer.check_rbac(user, action)
        if decision.allowed:
            return user

        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Access denied: {decision.reason}",
        )

    return _check_action


async def check_assessment_access(
    user: AuthUser,
    assessment_id: str,
    classification: Classification = Classification.INTERNAL,
    action: AuditAction = AuditAction.ACCESSED,
    source_ip: str = "",
) -> bool:
    """RBAC + ABAC check for assessment access. Returns True if allowed.

    Logs the access attempt to the audit trail (NEN 7513).
    """
    if not _authorizer:
        return True

    rbac = _authorizer.check_rbac(user, Action.VIEW_ASSESSMENT)
    if not rbac.allowed:
        await _log_access(
            user, assessment_id, action, "denied:rbac", rbac.reason, source_ip
        )
        return False

    abac = _authorizer.check_abac(user, classification)
    if not abac.allowed:
        await _log_access(
            user, assessment_id, action, "denied:abac", abac.reason, source_ip
        )
        return False

    await _log_access(user, assessment_id, action, "allowed", "", source_ip)
    return True


async def _log_access(
    user: AuthUser,
    assessment_id: str,
    action: AuditAction,
    result: str,
    reason: str,
    source_ip: str,
):
    """Log access attempt to audit trail and forward to SIEM if configured."""
    if not _audit_logger:
        return

    entry = audit_assessment_access(
        user=user,
        assessment_id=assessment_id,
        action=action,
        source_ip=source_ip,
    )
    entry.details["result"] = result
    entry.details["reason"] = reason
    await _audit_logger.log(entry)

    if _siem_forwarder:
        try:
            await _siem_forwarder.send(entry)
        except Exception as e:
            logger.warning(f"SIEM forward failed: {e}")
