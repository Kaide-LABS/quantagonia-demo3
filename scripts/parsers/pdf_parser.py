import pdfplumber
import sys

# Assume ParsedDocument is returned as a dict that matches the schema in gemini_client.py
def parse_pdf(file_path: str) -> dict:
    tables = []
    sections = []
    full_text = ""
    
    try:
        with pdfplumber.open(file_path) as pdf:
            num_pages = len(pdf.pages)
            for i, page in enumerate(pdf.pages):
                text = page.extract_text()
                if text:
                    full_text += text + "\n"
                    # Simple heuristic: text blocks are just sections for now
                    sections.append({
                        "heading": None,
                        "content": text,
                        "page_start": i+1,
                        "page_end": i+1
                    })
                
                extracted_tables = page.extract_tables()
                for table in extracted_tables:
                    if not table or not table[0]:
                        continue
                    tables.append({
                        "page": i+1,
                        "headers": [str(x) for x in table[0]],
                        "rows": [[str(x) for x in row] for row in table[1:] if any(row)]
                    })
                    
        return {
            "filename": file_path.split('/')[-1],
            "doc_type": "pdf_contract",
            "pages": num_pages,
            "full_text": full_text,
            "tables": tables,
            "sections": sections,
            "metadata": {}
        }
    except Exception as e:
        print(f"Failed to parse PDF {file_path}: {e}", file=sys.stderr)
        return None
