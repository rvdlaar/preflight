"""
Preflight AuthN — Entra ID OIDC token validation.

Validates JWT access tokens from Microsoft Entra ID.
Extracts user identity (entra_id, display_name) and group membership.
Maps Entra ID groups to Preflight RBAC roles.

Phase 1 supports both:
  - Entra ID OIDC (production)
  - API key + dev mode (local testing)
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class AuthUser:
    entra_id: str
    display_name: str
    email: str
    role: str = "requestor"
    department: str = ""
    clearance_level: str = "internal"
    clinical_access: bool = False
    groups: list[str] = field(default_factory=list)
    language: str = "nl"

    @property
    def is_authenticated(self) -> bool:
        return bool(self.entra_id)

    @property
    def is_architect(self) -> bool:
        return self.role in ("architect", "lead-architect", "chief-architect")

    @property
    def is_board(self) -> bool:
        return self.role in ("board-member", "board-chair")

    @property
    def is_authority(self) -> bool:
        return self.role in ("compliance-officer", "fg-dpo")


ROLE_HIERARCHY: dict[str, set[str]] = {
    "admin": {
        "admin",
        "chief-architect",
        "cio",
        "architect",
        "lead-architect",
        "board-chair",
        "board-member",
        "compliance-officer",
        "fg-dpo",
        "requestor",
    },
    "chief-architect": {"chief-architect", "architect", "lead-architect", "requestor"},
    "cio": {"cio", "requestor"},
    "lead-architect": {"lead-architect", "architect", "requestor"},
    "architect": {"architect", "requestor"},
    "board-chair": {"board-chair", "board-member", "requestor"},
    "board-member": {"board-member", "requestor"},
    "compliance-officer": {"compliance-officer", "requestor"},
    "fg-dpo": {"fg-dpo", "requestor"},
    "requestor": {"requestor"},
}

VALID_ROLES = set(ROLE_HIERARCHY.keys())


class RoleMapper:
    """Map Entra ID group IDs to Preflight roles.

    INVERSION: What if group mapping is wrong?
      → A user gets admin when they shouldn't, or can't access when they should.
      → Mitigation: mapping is configurable, not hardcoded. Default is conservative
        (unknown groups → requestor). Admin mapping requires explicit configuration.
    """

    def __init__(self, group_role_map: dict[str, str] | None = None):
        self._group_map: dict[str, str] = group_role_map or {}

    def map_groups_to_role(self, group_ids: list[str]) -> str:
        """Map Entra ID groups to a Preflight role.

        Takes the highest-privilege role from the user's groups.
        Unknown groups are ignored (conservative default).
        """
        roles: set[str] = set()
        for gid in group_ids:
            if gid in self._group_map:
                roles.add(self._group_map[gid])

        if not roles:
            return "requestor"

        for highest in (
            "admin",
            "chief-architect",
            "cio",
            "lead-architect",
            "board-chair",
            "compliance-officer",
            "fg-dpo",
            "architect",
            "board-member",
            "requestor",
        ):
            if highest in roles:
                return highest

        return "requestor"

    def has_role(self, user_role: str, required_role: str) -> bool:
        """Check if user_role is authorized for required_role (hierarchical)."""
        permitted = ROLE_HIERARCHY.get(user_role, {"requestor"})
        return required_role in permitted


@dataclass
class TokenConfig:
    tenant_id: str = ""
    client_id: str = ""
    jwks_url: str = ""
    issuer: str = ""
    audience: str = ""
    clock_skew_seconds: int = 300


def build_token_config(
    tenant_id: str = "",
    client_id: str = "",
) -> TokenConfig:
    """Build TokenConfig from Entra ID tenant and client IDs."""
    if not tenant_id or not client_id:
        return TokenConfig()

    return TokenConfig(
        tenant_id=tenant_id,
        client_id=client_id,
        jwks_url=f"https://login.microsoftonline.com/{tenant_id}/discovery/v2.0/keys",
        issuer=f"https://login.microsoftonline.com/{tenant_id}/v2.0",
        audience=client_id,
    )


class EntraIDValidator:
    """Validate Entra ID JWT access tokens.

    FIRST PRINCIPLE: We don't build auth. We trust Entra ID's signatures
    and extract identity from validated tokens.

    SECOND ORDER: If Entra ID is down, nobody can authenticate.
    That's correct — if the identity provider is down, you don't want
    people accessing architecture assessments through a back door.
    """

    def __init__(self, config: TokenConfig, role_mapper: RoleMapper):
        self.config = config
        self.role_mapper = role_mapper
        self._jwks_cache: dict | None = None
        self._jwks_cached_at: float = 0

    def _is_configured(self) -> bool:
        return bool(self.config.tenant_id and self.config.client_id)

    async def validate_token(self, token: str) -> AuthUser | None:
        """Validate an Entra ID access token and return user info.

        Returns None if validation fails (expired, invalid signature, wrong audience).
        """
        if not self._is_configured():
            return None

        try:
            import jwt as pyjwt

            jwks = await self._get_jwks()
            if not jwks:
                return None

            unverified_header = pyjwt.get_unverified_header(token)
            kid = unverified_header.get("kid")

            signing_key = None
            for key in jwks.get("keys", []):
                if key.get("kid") == kid:
                    from jwt.algorithms import RSAAlgorithm

                    signing_key = RSAAlgorithm.from_jwk(json.dumps(key))
                    break

            if not signing_key:
                return None

            payload = pyjwt.decode(
                token,
                signing_key,
                algorithms=["RS256"],
                audience=self.config.audience,
                issuer=self.config.issuer,
                options={
                    "require": ["exp", "iat", "sub"],
                    "leeway": self.config.clock_skew_seconds,
                },
            )

            entra_id = payload.get("preferred_username") or payload.get("sub", "")
            display_name = payload.get("name", entra_id)
            email = payload.get("email", entra_id)
            groups = payload.get("groups", [])

            if not isinstance(groups, list):
                groups = []

            role = self.role_mapper.map_groups_to_role(groups)

            clinical_access = role in (
                "architect",
                "lead-architect",
                "chief-architect",
                "cmio",
                "fg-dpo",
                "compliance-officer",
            )

            return AuthUser(
                entra_id=entra_id,
                display_name=display_name,
                email=email,
                role=role,
                clinical_access=clinical_access,
                groups=groups,
            )

        except Exception:
            return None

    async def _get_jwks(self) -> dict | None:
        """Fetch JWKS from Entra ID with caching (TTL: 1 hour)."""
        now = time.time()
        if self._jwks_cache and (now - self._jwks_cached_at) < 3600:
            return self._jwks_cache

        if not self.config.jwks_url:
            return None

        try:
            import httpx

            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(self.config.jwks_url)
                resp.raise_for_status()
                self._jwks_cache = resp.json()
                self._jwks_cached_at = now
                return self._jwks_cache
        except Exception:
            return self._jwks_cache

    def invalidate_jwks_cache(self):
        self._jwks_cache = None
        self._jwks_cached_at = 0


class DevApiKeyValidator:
    """Phase 1 dev mode — API key authentication for local testing.

    FIRST PRINCIPLE: No production system should ever use this.
    This exists so developers can test the API without Entra ID.
    API keys are mapped to roles. No passwords.

    INVERSION: What if someone deploys dev mode to production?
      → Explicit check: DevApiKeyValidator only works when PREFLIGHT_DEV_MODE=1
      → Startup logs a loud warning
    """

    def __init__(
        self,
        api_keys: dict[str, AuthUser] | None = None,
        keys_file: str | Path | None = None,
    ):
        self._keys: dict[str, AuthUser] = api_keys or {}

        if keys_file:
            self._load_keys_file(Path(keys_file))

        if not self._keys:
            self._keys = {
                "dev-admin": AuthUser(
                    entra_id="dev-admin@localhost",
                    display_name="Dev Admin",
                    email="dev-admin@localhost",
                    role="admin",
                    clinical_access=True,
                ),
                "dev-architect": AuthUser(
                    entra_id="dev-architect@localhost",
                    display_name="Dev Architect",
                    email="dev-architect@localhost",
                    role="architect",
                    clinical_access=True,
                ),
                "dev-requestor": AuthUser(
                    entra_id="dev-requestor@localhost",
                    display_name="Dev Requestor",
                    email="dev-requestor@localhost",
                    role="requestor",
                ),
            }

    def _load_keys_file(self, path: Path):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            for key, user_data in data.items():
                self._keys[key] = AuthUser(
                    entra_id=user_data.get("entra_id", f"{key}@localhost"),
                    display_name=user_data.get("display_name", key),
                    email=user_data.get("email", f"{key}@localhost"),
                    role=user_data.get("role", "requestor"),
                    department=user_data.get("department", ""),
                    clearance_level=user_data.get("clearance_level", "internal"),
                    clinical_access=user_data.get("clinical_access", False),
                )
        except Exception:
            pass

    def validate_key(self, api_key: str) -> AuthUser | None:
        user = self._keys.get(api_key)
        if user:
            return AuthUser(
                entra_id=user.entra_id,
                display_name=user.display_name,
                email=user.email,
                role=user.role,
                department=user.department,
                clearance_level=user.clearance_level,
                clinical_access=user.clinical_access,
                groups=user.groups,
                language=user.language,
            )
        return None


@dataclass
class AuthConfig:
    """Authentication configuration.

    Loaded from environment variables or a config file.
    """

    dev_mode: bool = False
    tenant_id: str = ""
    client_id: str = ""
    group_role_map: dict[str, str] = field(default_factory=dict)
    api_keys_file: str = ""

    @classmethod
    def from_env(cls) -> AuthConfig:
        import os

        return cls(
            dev_mode=os.environ.get("PREFLIGHT_DEV_MODE", "") == "1",
            tenant_id=os.environ.get("PREFLIGHT_ENTRA_TENANT_ID", ""),
            client_id=os.environ.get("PREFLIGHT_ENTRA_CLIENT_ID", ""),
            group_role_map=_load_group_map(os.environ.get("PREFLIGHT_GROUP_MAP", "")),
            api_keys_file=os.environ.get("PREFLIGHT_API_KEYS_FILE", ""),
        )


def _load_group_map(env_val: str) -> dict[str, str]:
    """Load group-role mapping from env var (JSON format)."""
    if not env_val:
        return {}
    try:
        return json.loads(env_val)
    except json.JSONDecodeError:
        return {}
