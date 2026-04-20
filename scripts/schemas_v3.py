from typing import List, Dict, Any, Literal, Optional
from datetime import datetime
from pydantic import BaseModel, Field

class TenantConfig(BaseModel):
    tenant_id: str = Field(..., pattern=r'^[a-z0-9_-]+$')
    display_name: str
    workspace_path: str
    budget_monthly_minutes: Optional[int] = None
    budget_alert_threshold: float = 0.8
    allowed_planners: List[str] = Field(..., min_length=1)
    gemini_rate_limit_rpm: int = 30
    solver_concurrency: int = 2
    created_at: datetime
    active: bool = True

class CostRecord(BaseModel):
    id: str
    tenant_id: str
    request_id: str
    stage_id: Optional[str] = None
    job_id: str
    billed_minutes: int
    submitted_at: datetime
    completed_at: Optional[datetime] = None
    status: str
    objective: Optional[float] = None

class BudgetSummary(BaseModel):
    tenant_id: str
    period: str
    total_minutes_used: int
    budget_limit: Optional[int] = None
    budget_remaining: Optional[int] = None
    jobs_submitted: int
    jobs_succeeded: int
    jobs_failed: int
    alert_triggered: bool

class PipelineEvent(BaseModel):
    timestamp: datetime
    tenant_id: str
    request_id: str
    event_type: str
    details: Dict[str, Any]
    duration_ms: Optional[int] = None

class ServiceHealth(BaseModel):
    available: bool
    latency_ms: Optional[int] = None
    error_rate_5m: float
    circuit_open: bool

class HealthStatus(BaseModel):
    status: Literal["healthy", "degraded", "unhealthy"]
    gemini_flash: ServiceHealth
    gemini_pro: ServiceHealth
    hybridsolver: ServiceHealth
    slack: ServiceHealth
    disk_usage_percent: float
    active_jobs: int
    checked_at: datetime
