import os
from fastapi import FastAPI, Depends, Request
from auth import verify_token, UserAuth

app = FastAPI(title="DecisionAI V1 API")

@app.get("/v1/health")
async def health_check():
    return {"status": "healthy"}

@app.post("/v1/requests")
async def create_request(req: Request, user: UserAuth = Depends(verify_token)):
    """
    Creates a new optimization request. (FDE Mock)
    """
    if user.role == "viewer":
        return {"error": "Unauthorized. Viewers cannot submit requests."}, 403
        
    return {"message": "Request queued", "tenant_id": user.tenant_id}

@app.patch("/v1/requests/{id}/approve")
async def approve_request(id: str, req: Request, user: UserAuth = Depends(verify_token)):
    if user.role == "viewer":
        return {"error": "Unauthorized. Viewers cannot approve requests."}, 403
    return {"message": f"Request {id} approved for submission"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
