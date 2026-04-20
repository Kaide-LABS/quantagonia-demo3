import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from fastapi import FastAPI, Depends, Request, HTTPException, Header
from typing import Optional
from auth import verify_token, UserAuth

app = FastAPI(title="DecisionAI V1 API")


async def get_current_user(authorization: Optional[str] = Header(None)) -> UserAuth:
    return await verify_token(authorization)


@app.get("/v1/health")
async def health_check():
    return {"status": "healthy"}


@app.post("/v1/requests")
async def create_request(req: Request, user: UserAuth = Depends(get_current_user)):
    """Creates a new optimization request."""
    if user.role == "viewer":
        raise HTTPException(status_code=403, detail="Viewers cannot submit requests.")
    return {"message": "Request queued", "tenant_id": user.tenant_id}


@app.patch("/v1/requests/{id}/approve")
async def approve_request(id: str, req: Request, user: UserAuth = Depends(get_current_user)):
    if user.role == "viewer":
        raise HTTPException(status_code=403, detail="Viewers cannot approve requests.")
    return {"message": f"Request {id} approved for submission"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
