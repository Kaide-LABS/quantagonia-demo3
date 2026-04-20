import json
import sys
import os
from datetime import datetime
from pydantic import ValidationError
from schemas import (
    ConstraintBundle, ValidationReport, ValidationError_, ValidationWarning, 
    UnitConversion, BundleStats
)

UNIT_ALIASES = {
    'mass': {'canonical': 'kg', 'aliases': {'tons': 1000.0, 'lbs': 0.453592, 'g': 0.001, 'kg': 1.0}},
    'time': {'canonical': 'hours', 'aliases': {'minutes': 1/60.0, 'days': 24.0, 'shifts': 8.0, 'hours': 1.0}},
    'volume': {'canonical': 'liters', 'aliases': {'m3': 1000.0, 'gallons': 3.78541, 'liters': 1.0}},
    'currency': {'canonical': 'EUR', 'aliases': {'EUR': 1.0}}
}

def validate_and_normalize(run_dir: str):
    bundle_path = os.path.join(run_dir, 'constraint_bundle.json')
    report_path = os.path.join(run_dir, 'validation_report.json')
    
    if not os.path.exists(bundle_path):
        print("Fatal: constraint_bundle.json not found.", file=sys.stderr)
        sys.exit(2)
        
    with open(bundle_path, 'r') as f:
        raw = f.read()

    errors = []
    warnings = []
    conversions = []

    try:
        bundle = ConstraintBundle.model_validate_json(raw)
    except ValidationError as e:
        for err in e.errors():
            errors.append(ValidationError_(
                code="SCHEMA_INVALID",
                message=err['msg'],
                path=".".join(map(str, err['loc']))
            ))
        # Cannot proceed further if schema is invalid
        report = ValidationReport(
            request_id="unknown", passed=False, errors=errors, warnings=warnings, 
            unit_conversions=conversions,
            stats=BundleStats(num_variables=0, num_continuous=0, num_integer=0, num_binary=0, num_constraints=0, num_objective_terms=0, density=0.0),
            validated_at=datetime.utcnow()
        )
        with open(report_path, 'w') as f:
            f.write(report.model_dump_json(indent=2))
        print(json.dumps({"passed": False, "errors": len(errors), "warnings": 0}))
        sys.exit(1)

    # Impossible Value Rejection & Warnings
    var_dict = {v.id: v for v in bundle.variables}
    used_vars = set([t.variable_id for t in bundle.objective.terms])
    
    for v in bundle.variables:
        if v.lower_bound is not None and v.lower_bound < 0:
            name_lower = v.name.lower()
            if any(x in name_lower for x in ["capacity", "demand", "quantity"]):
                errors.append(ValidationError_(
                    code="IMPOSSIBLE_VALUE",
                    message="Negative capacity/demand not allowed",
                    path=f"variables.{v.id}.lower_bound"
                ))
        if v.unit and v.unit.unit == '%':
            if (v.upper_bound and v.upper_bound > 100) or (v.lower_bound and v.lower_bound < 0):
                errors.append(ValidationError_(
                    code="IMPOSSIBLE_VALUE",
                    message="Percentage outside [0, 100]",
                    path=f"variables.{v.id}"
                ))

    for c in bundle.constraints:
        used_vars.update([coef.variable_id for coef in c.lhs])
        if abs(c.rhs) > 1e9:
            warnings.append(ValidationWarning(
                code="LARGE_COEFFICIENT",
                message=f"RHS > 1e9 in constraint {c.id}",
                path=f"constraints.{c.id}.rhs"
            ))
        for coef in c.lhs:
            if abs(coef.value) > 1e9:
                warnings.append(ValidationWarning(
                    code="LARGE_COEFFICIENT",
                    message=f"Value > 1e9 for {coef.variable_id} in constraint {c.id}",
                    path=f"constraints.{c.id}.lhs.{coef.variable_id}"
                ))
        if c.confidence < 0.7:
            warnings.append(ValidationWarning(
                code="LOW_CONFIDENCE",
                message="Low confidence constraint",
                path=f"constraints.{c.id}"
            ))

    for v in bundle.variables:
        if v.confidence < 0.7:
            warnings.append(ValidationWarning(
                code="LOW_CONFIDENCE",
                message="Low confidence variable",
                path=f"variables.{v.id}"
            ))
        if v.id not in used_vars:
            warnings.append(ValidationWarning(
                code="UNUSED_VARIABLE",
                message="Variable not in any constraint or objective",
                path=f"variables.{v.id}"
            ))

    # Unit normalization
    if not bundle.units_normalized:
        for v in bundle.variables:
            if v.unit and v.unit.quantity in UNIT_ALIASES:
                qty_spec = UNIT_ALIASES[v.unit.quantity]
                if v.unit.unit != qty_spec['canonical'] and v.unit.unit in qty_spec['aliases']:
                    factor = qty_spec['aliases'][v.unit.unit]
                    # Update coefficients and bounds
                    if v.lower_bound is not None:
                        v.lower_bound *= factor
                    if v.upper_bound is not None:
                        v.upper_bound *= factor
                        
                    affected_cons = []
                    # Update constraints where this variable appears
                    for c in bundle.constraints:
                        for coef in c.lhs:
                            if coef.variable_id == v.id:
                                # if var is multiplied by factor, the coef should be divided to maintain balance, 
                                # or wait, if we change the unit of the variable from tons to kg, then x_tons = x_kg / 1000.
                                # So c * x_tons = c * (x_kg / 1000) = (c/1000) * x_kg. So coef value must be divided by factor.
                                coef.value /= factor
                                affected_cons.append(c.id)
                                
                    # Objective terms
                    for term in bundle.objective.terms:
                        if term.variable_id == v.id:
                            term.coefficient /= factor
                            
                    v.unit.normalized_to = qty_spec['canonical']
                    v.unit.conversion_factor = factor
                    
                    conversions.append(UnitConversion(
                        variable_id=v.id,
                        from_unit=v.unit.unit,
                        to_unit=qty_spec['canonical'],
                        factor=factor,
                        affected_constraints=affected_cons
                    ))
                    
        if conversions:
            bundle.units_normalized = True
            bundle.normalization_log.append(f"Normalized {len(conversions)} variables to canonical units.")

    passed = len(errors) == 0

    num_vars = len(bundle.variables)
    num_cons = len(bundle.constraints)
    non_zeros = sum(len(c.lhs) for c in bundle.constraints)
    density = non_zeros / (num_vars * num_cons) if num_vars and num_cons else 0.0

    stats = BundleStats(
        num_variables=num_vars,
        num_continuous=sum(1 for v in bundle.variables if v.type == "continuous"),
        num_integer=sum(1 for v in bundle.variables if v.type == "integer"),
        num_binary=sum(1 for v in bundle.variables if v.type == "binary"),
        num_constraints=num_cons,
        num_objective_terms=len(bundle.objective.terms),
        density=density
    )

    report = ValidationReport(
        request_id=bundle.request_id,
        passed=passed,
        errors=errors,
        warnings=warnings,
        unit_conversions=conversions,
        stats=stats,
        validated_at=datetime.utcnow()
    )

    with open(report_path, 'w') as f:
        f.write(report.model_dump_json(indent=2))

    if passed:
        with open(bundle_path, 'w') as f:
            f.write(bundle.model_dump_json(indent=2))
        print(json.dumps({"passed": True, "errors": 0, "warnings": len(warnings)}))
        sys.exit(0)
    else:
        print(json.dumps({"passed": False, "errors": len(errors), "warnings": len(warnings)}))
        sys.exit(1)

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: validate_bundle.py <run_dir>", file=sys.stderr)
        sys.exit(2)
    validate_and_normalize(sys.argv[1])
