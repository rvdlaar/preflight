"""
Preflight authentication — Microsoft Entra ID (Azure AD) OIDC integration.

FIRST PRINCIPLE: The hospital already has an identity provider. We do NOT
build auth. We validate tokens from Entra ID and extract user identity + roles.

Design decisions:
- JWT validation via JWKS — no custom passwords, no user registration
- RBAC roles come from Entra ID group membership (configurable mapping)
- Token refresh is the client's responsibility — we validate on every request
- Phase 1: configurable dev mode with API key for local testing
- Role mapping is a config file, not hardcoded — hospitals differ in Entra ID setup

INVERSION: What makes auth fail?
  - Clock skew between our server and Entra ID → 5-minute leeway
  - Entra ID being down → cached JWKS with TTL, not hard fail
  - Token replay → validate `jti` claim on write operations
  - Stale group membership → refresh roles from Entra ID on each token
"""
