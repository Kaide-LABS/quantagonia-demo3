from enum import StrEnum
from typing import List, Optional, Dict, Any, Literal
from datetime import datetime
from pydantic import BaseModel, Field, model_validator, field_validator

class VariableType(StrEnum):
    CONTINUOUS = "continuous"
    INTEGER = "integer"
    BINARY = "binary"

class ConstraintOperator(StrEnum):
    LEQ = "<="
    GEQ = ">="
    EQ = "=="

class ObjectiveSense(StrEnum):
    MINIMIZE = "minimize"
    MAXIMIZE = "maximize"

class UnitSpec(BaseModel):
    quantity: str
    unit: str
    normalized_to: Optional[str] = None
    conversion_factor: Optional[float] = None

class DecisionVariable(BaseModel):
    id: str = Field(..., min_length=1, pattern=r'^[a-zA-Z_][a-zA-Z0-9_]*$')
    name: str
    type: VariableType
    lower_bound: Optional[float] = 0.0
    upper_bound: Optional[float] = None
    unit: Optional[UnitSpec] = None
    source_file: str
    confidence: float = Field(..., ge=0.0, le=1.0)

    @field_validator('id')
    def reject_reserved(cls, v):
        reserved = {'ROWS', 'COLUMNS', 'RHS', 'BOUNDS', 'RANGES', 'OBJSENSE'}
        if v in reserved:
            raise ValueError(f"ID cannot be an MPS reserved word: {v}")
        return v

    @model_validator(mode='after')
    def check_bounds(self):
        if self.lower_bound is not None and self.upper_bound is not None:
            if self.lower_bound > self.upper_bound:
                raise ValueError("lower_bound must be <= upper_bound")
        if self.type == VariableType.BINARY:
            if self.lower_bound not in (None, 0.0):
                raise ValueError("Binary variable lower bound must be 0 or None")
            if self.upper_bound not in (None, 1.0):
                raise ValueError("Binary variable upper bound must be 1 or None")
        return self

class Coefficient(BaseModel):
    variable_id: str
    value: float

class Constraint(BaseModel):
    id: str = Field(..., min_length=1, pattern=r'^[a-zA-Z_][a-zA-Z0-9_]*$')
    name: str
    lhs: List[Coefficient] = Field(..., min_length=1)
    operator: ConstraintOperator
    rhs: float
    source_file: str
    source_text: Optional[str] = None
    is_inferred: bool = False
    confidence: float = Field(..., ge=0.0, le=1.0)

    @field_validator('lhs')
    def unique_vars_in_lhs(cls, lhs):
        seen = set()
        for coef in lhs:
            if coef.variable_id in seen:
                raise ValueError(f"Duplicate variable in LHS: {coef.variable_id}")
            seen.add(coef.variable_id)
        return lhs

    @field_validator('rhs')
    def warn_large_rhs(cls, v):
        return v

class ObjectiveTerm(BaseModel):
    variable_id: str
    coefficient: float

class Objective(BaseModel):
    sense: ObjectiveSense
    terms: List[ObjectiveTerm] = Field(..., min_length=1)
    constant: float = 0.0
    description: str

class ConstraintBundle(BaseModel):
    request_id: str
    account: str
    created_at: datetime
    source_files: List[str] = Field(..., min_length=1)
    variables: List[DecisionVariable] = Field(..., min_length=1)
    constraints: List[Constraint] = Field(..., min_length=1)
    objective: Objective
    units_normalized: bool = False
    normalization_log: List[str] = []
    ambiguities: List[str] = []
    metadata: Dict[str, Any] = {}

    @model_validator(mode='after')
    def check_referential_integrity(self):
        var_ids = {v.id for v in self.variables}
        if len(var_ids) != len(self.variables):
            raise ValueError("Duplicate variable ids found")
            
        con_ids = {c.id for c in self.constraints}
        if len(con_ids) != len(self.constraints):
            raise ValueError("Duplicate constraint ids found")

        for c in self.constraints:
            for term in c.lhs:
                if term.variable_id not in var_ids:
                    raise ValueError(f"Dangling variable ref in constraint {c.id}: {term.variable_id}")
                    
        for term in self.objective.terms:
            if term.variable_id not in var_ids:
                raise ValueError(f"Dangling variable ref in objective: {term.variable_id}")
                
        return self

class ValidationError_(BaseModel):
    code: str
    message: str
    path: str
    severity: Literal["error"] = "error"

class ValidationWarning(BaseModel):
    code: str
    message: str
    path: str
    severity: Literal["warning"] = "warning"

class UnitConversion(BaseModel):
    variable_id: str
    from_unit: str
    to_unit: str
    factor: float
    affected_constraints: List[str]

class BundleStats(BaseModel):
    num_variables: int
    num_continuous: int
    num_integer: int
    num_binary: int
    num_constraints: int
    num_objective_terms: int
    density: float

class ValidationReport(BaseModel):
    request_id: str
    passed: bool
    errors: List[ValidationError_] = []
    warnings: List[ValidationWarning] = []
    unit_conversions: List[UnitConversion] = []
    stats: BundleStats
    validated_at: datetime

class SubmissionRecord(BaseModel):
    request_id: str
    job_id: str
    submitted_at: datetime
    input_file: str
    params: Dict[str, Any]
    status: str
    objective: Optional[float] = None
    bound: Optional[float] = None
    rel_gap: Optional[float] = None
    wall_time: Optional[float] = None
    billed_minutes: Optional[int] = None
