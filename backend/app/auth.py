from typing import Annotated

from fastapi import Header, HTTPException, status

from .config import get_settings


Role = Annotated[str, Header(alias="X-User-Role")]


# ---------------------------------------------------------------------------
# DEVELOPMENT-ONLY identity boundary.
#
# The X-User-Role header carries NO authentication: any caller can claim any
# role, and there is no user identity, so per-patient record ownership cannot
# be enforced server-side yet. This is acceptable only for local development.
#
# PRODUCTION BOUNDARY (must be implemented before real data):
#   1. Replace this dependency with validated JWT claims (issuer, audience,
#      expiry, signature) issued by the identity provider.
#   2. Enforce ownership: a patient token may only touch records whose
#      patient_id matches the token subject; doctors only patients under
#      their care (care-team/tenant mapping).
#   3. Until that exists, this dependency REFUSES every request when
#      APP_ENV != "development", so the API cannot be accidentally deployed
#      with header auth.
# ---------------------------------------------------------------------------
def require_role(*allowed: str):
    def dependency(role: Role = "patient") -> str:
        if get_settings().app_env != "development":
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Authentication is not configured. The X-User-Role header is a development-only boundary.",
            )
        if role not in allowed:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Role not permitted")
        return role
    return dependency
