from typing import Annotated

from fastapi import Header, HTTPException, status


Role = Annotated[str, Header(alias="X-User-Role")]


def require_role(*allowed: str):
    def dependency(role: Role = "patient") -> str:
        if role not in allowed:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Role not permitted")
        return role
    return dependency
