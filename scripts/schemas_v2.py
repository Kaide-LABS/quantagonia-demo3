from typing import List, Dict, Any, Literal, Optional
from datetime import datetime
from pydantic import BaseModel, Field, model_validator

class StageDefinition(BaseModel):
    stage_id: str = Field(..., pattern=r'^[a-zA-Z0-9_-]+$')
    stage_order: int = Field(..., ge=1)
    depends_on: List[str] = []
    input_files: List[str] = Field(..., min_length=1)
    carry_forward_variables: List[str] = []
    time_limit_override: Optional[int] = None
    qubo_eligible: bool = False

class DecompositionPlan(BaseModel):
    plan_id: str
    account: str
    description: str
    stages: List[StageDefinition] = Field(..., min_length=2)
    global_params: Dict[str, Any] = {}
    carry_forward_strategy: Literal["ending_inventory", "custom_variables", "full_solution"]
    created_at: datetime

    @model_validator(mode='after')
    def validate_plan(self):
        stage_ids = set()
        for stage in self.stages:
            if stage.stage_id in stage_ids:
                raise ValueError(f"Duplicate stage_id: {stage.stage_id}")
            stage_ids.add(stage.stage_id)
            for dep in stage.depends_on:
                if dep not in stage_ids:
                    # Note: this enforces that dependencies are listed BEFORE the stage in the file
                    # which is a simple way to avoid cycles and ensure valid order
                    raise ValueError(f"Unknown or circular dependency {dep} in stage {stage.stage_id}")
        orders = [s.stage_order for s in self.stages]
        if sorted(orders) != list(range(1, len(self.stages) + 1)):
            raise ValueError("stage_order must be sequential starting from 1")
        return self

class QuboComparisonResult(BaseModel):
    qubo_job_id: str
    qubo_objective: Optional[float] = None
    qubo_wall_time: Optional[float] = None
    qubo_billed_minutes: Optional[int] = None
    mip_wins: bool
    recommendation: Literal["prefer_mip", "prefer_qubo", "inconclusive"]

class StageResult(BaseModel):
    stage_id: str
    job_id: str
    status: Literal["success", "timeout", "error", "reformulated", "skipped"]
    objective: Optional[float] = None
    bound: Optional[float] = None
    rel_gap: Optional[float] = None
    wall_time: Optional[float] = None
    billed_minutes: int
    solution: Dict[str, float] = {}
    carry_forward_values: Dict[str, float] = {}
    qubo_attempted: bool = False
    qubo_result: Optional[QuboComparisonResult] = None
    reformulation_attempts: int = 0
    memory_entries: List[str] = []

class PlanExecutionReport(BaseModel):
    plan_id: str
    account: str
    started_at: datetime
    completed_at: Optional[datetime] = None
    stages_completed: int = 0
    stages_total: int
    total_billed_minutes: int = 0
    total_wall_time: float = 0.0
    stage_results: List[StageResult] = []
    overall_status: Literal["completed", "partial", "failed", "running"]
    memory_entries_written: int = 0

class ReformulationAction(BaseModel):
    action_type: Literal["tighten_presolve", "relax_gap", "try_qubo", "increase_time", "decompose_further"]
    rationale: str
    param_changes: Dict[str, Any]
    attempt_number: int
