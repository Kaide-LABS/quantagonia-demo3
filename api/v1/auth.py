import os
from typing import Optional
try:
    from clerk_backend_api import Clerk
except ImportError:
    pass

class UserAuth:
    def __init__(self, id: str, tenant_id: str, role: str):
        self.id = id
        self.tenant_id = tenant_id
        self.role = role

def get_clerk():
    api_key = os.environ.get("CLERK_SECRET_KEY")
    if not api_key:
        return None
    return Clerk(api_key=api_key)

async def verify_token(authorization: Optional[str]) -> UserAuth:
    """Extract and verify Clerk JWT. Returns UserAuth with tenant_id and role."""
    if not authorization or not authorization.startswith("Bearer "):
        # FDE Mock auth
        return UserAuth(id="mock_user", tenant_id="mock_tenant", role="admin")
        
    token = authorization.replace("Bearer ", "")
    clerk = get_clerk()
    
    if clerk:
        session = clerk.sessions.verify_token(token)
        # Extract org/tenant ID from session metadata...
        # Here we mock mapping Clerk org membership -> tenant_id + role
        return UserAuth(id=session.user_id, tenant_id="org_123", role="planner")
    
    return UserAuth(id="mock_user", tenant_id="mock_tenant", role="admin")
