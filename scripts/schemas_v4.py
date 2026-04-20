from typing import List, Literal, Optional
from datetime import datetime
from pydantic import BaseModel

class User(BaseModel):
    id: str
    email: str
    name: str
    tenant_id: str
    role: Literal["admin", "planner", "viewer"]
    created_at: datetime
    stripe_customer_id: Optional[str] = None

class BillingPlan(BaseModel):
    plan_id: str
    name: str
    included_minutes: int
    overage_rate_per_minute: float
    max_concurrent_jobs: int
    max_file_upload_mb: int
    features: List[str]

class Invoice(BaseModel):
    id: str
    tenant_id: str
    period: str
    included_minutes: int
    used_minutes: int
    overage_minutes: int
    overage_cost: float
    total_cost: float
    stripe_invoice_id: Optional[str] = None
    status: Literal["draft", "open", "paid", "void"]

class UploadedFile(BaseModel):
    filename: str
    s3_key: str
    size_bytes: int
    content_type: str
    uploaded_at: datetime

class JobRequest(BaseModel):
    id: str
    tenant_id: str
    user_id: str
    title: str
    files: List[UploadedFile]
    instructions: Optional[str] = None
    strategy: Literal["auto", "single", "quarterly"]
    priority: Literal["normal", "high"]
    status: Literal["queued", "processing", "awaiting_approval", "submitted", "completed", "failed"]
    created_at: datetime

class QualityFeedback(BaseModel):
    request_id: str
    tenant_id: str
    extraction_quality: Literal["good", "acceptable", "poor"]
    solver_outcome: Literal["optimal", "feasible", "infeasible", "timeout"]
    issues: List[str]
    corrective_prompt_additions: List[str]
    timestamp: datetime
