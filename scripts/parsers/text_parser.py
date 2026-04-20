import sys

def parse_text(file_path: str) -> dict:
    try:
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            full_text = f.read()
            
        return {
            "filename": file_path.split('/')[-1],
            "doc_type": "text_instructions",
            "pages": 1,
            "full_text": full_text,
            "tables": [],
            "sections": [{
                "heading": "Document Start",
                "content": full_text,
                "page_start": 1,
                "page_end": 1
            }],
            "metadata": {}
        }
    except Exception as e:
        print(f"Failed to parse text {file_path}: {e}", file=sys.stderr)
        return None
