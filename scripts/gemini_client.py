import os
import sys
import json

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from pydantic import BaseModel
from typing import List, Literal, Optional

try:
    from google import genai
    from google.genai import types
except ImportError:
    print("google-genai package not installed", file=sys.stderr)
    sys.exit(1)

from schemas import ConstraintBundle

FLASH_MODEL = "gemini-3-flash"
PRO_MODEL = "gemini-3.1-pro"

class ClassifiedFile(BaseModel):
    filename: str
    detected_type: Literal["pdf_contract", "xlsx_data", "csv_data", "docx_text", "nl_instructions", "unknown"]
    parser_route: Literal["pdf_parser", "tabular_parser", "text_parser", "skip"]
    summary: str

class FileClassification(BaseModel):
    files: List[ClassifiedFile]
    missing_info: List[str]
    ambiguities: List[str]

class ParsedDocument(BaseModel):
    filename: str
    doc_type: str
    pages: int
    full_text: str
    tables: List[dict]
    sections: List[dict]
    metadata: dict = {}

def get_client():
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        print("GEMINI_API_KEY not set", file=sys.stderr)
        sys.exit(1)
    return genai.Client(api_key=api_key)

def classify_files(file_inventory: List[dict]) -> FileClassification:
    client = get_client()
    prompt = f"Classify the following files for an optimization modeling task:\\n{json.dumps(file_inventory, indent=2)}"
    
    response = client.models.generate_content(
        model=FLASH_MODEL,
        contents=prompt,
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=FileClassification,
            temperature=0.1
        )
    )
    return FileClassification.model_validate_json(response.text)

def extract_constraints(parsed_documents: List[ParsedDocument], prior_context: Optional[str]) -> ConstraintBundle:
    client = get_client()
    docs_json = json.dumps([d.model_dump() for d in parsed_documents], indent=2)
    prompt = "You are a mathematical optimization modeling assistant. Extract ONLY constraints explicitly stated or directly inferable from the provided documents. Mark inferred constraints with is_inferred=True. NEVER fabricate coefficients not present in source data. Set confidence scores honestly. If unsure, add to ambiguities list rather than guessing."
    if prior_context:
        prompt += f"\\n\\nPrior Context (MEMORY.md):\\n{prior_context}"
    prompt += f"\\n\\nDocuments:\\n{docs_json}"
    
    response = client.models.generate_content(
        model=PRO_MODEL,
        contents=prompt,
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=ConstraintBundle,
            temperature=0.1
        )
    )
    return ConstraintBundle.model_validate_json(response.text)

def repair_bundle(bundle_json: str, validation_errors: List[dict]) -> ConstraintBundle:
    client = get_client()
    prompt = f"Fix the following validation errors WITHOUT fabricating new data. Only restructure, correct types, or remove invalid entries.\\n\\nErrors:\\n{json.dumps(validation_errors, indent=2)}\\n\\nBundle:\\n{bundle_json}"
    
    response = client.models.generate_content(
        model=PRO_MODEL,
        contents=prompt,
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=ConstraintBundle,
            temperature=0.0
        )
    )
    return ConstraintBundle.model_validate_json(response.text)


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=["classify", "extract", "repair"])
    parser.add_argument("run_dir")
    args = parser.parse_args()

    if args.action == "classify":
        staging_dir = args.run_dir
        files = []
        for f in os.listdir(staging_dir):
            fp = os.path.join(staging_dir, f)
            if os.path.isfile(fp):
                files.append({"name": f, "size_bytes": os.path.getsize(fp), "extension": os.path.splitext(f)[1]})
        result = classify_files(files)
        print(result.model_dump_json(indent=2))

    elif args.action == "extract":
        parsed_path = os.path.join(args.run_dir, "parsed_docs.json")
        with open(parsed_path, 'r') as f:
            docs_raw = json.load(f)
        parsed_docs = [ParsedDocument(**d) for d in docs_raw]
        memory_path = os.path.join(os.path.dirname(args.run_dir), '..', '..', 'MEMORY.md')
        prior_context = None
        if os.path.exists(memory_path):
            with open(memory_path, 'r') as f:
                prior_context = f.read()
        bundle = extract_constraints(parsed_docs, prior_context)
        bundle_path = os.path.join(args.run_dir, "constraint_bundle.json")
        with open(bundle_path, 'w') as f:
            f.write(bundle.model_dump_json(indent=2))
        print(json.dumps({"status": "extracted", "variables": len(bundle.variables), "constraints": len(bundle.constraints)}))

    elif args.action == "repair":
        bundle_path = os.path.join(args.run_dir, "constraint_bundle.json")
        report_path = os.path.join(args.run_dir, "validation_report.json")
        with open(bundle_path, 'r') as f:
            bundle_json = f.read()
        with open(report_path, 'r') as f:
            report = json.load(f)
        repaired = repair_bundle(bundle_json, report.get("errors", []))
        with open(bundle_path, 'w') as f:
            f.write(repaired.model_dump_json(indent=2))
        print(json.dumps({"status": "repaired", "variables": len(repaired.variables), "constraints": len(repaired.constraints)}))
