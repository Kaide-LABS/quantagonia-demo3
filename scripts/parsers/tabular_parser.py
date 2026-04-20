import pandas as pd
import sys
import re

def detect_unit(header_name: str):
    # Match patterns like "Demand (kg)" or "Quantity [tons]" or "Amount_EUR"
    m = re.search(r'\((.*?)\)|\[(.*?)\]', header_name)
    if m:
        return m.group(1) or m.group(2)
    m2 = re.search(r'_([a-zA-Z]+)$', header_name)
    if m2:
        return m2.group(1)
    return None

def parse_tabular(file_path: str) -> dict:
    tables = []
    metadata = {"column_units": {}}
    
    try:
        if file_path.endswith('.xlsx'):
            xls = pd.ExcelFile(file_path, engine='openpyxl')
            for sheet_name in xls.sheet_names:
                df = pd.read_excel(xls, sheet_name=sheet_name)
                # Heuristic: assume first row is header
                headers = [str(x) for x in df.columns]
                
                for h in headers:
                    unit = detect_unit(h)
                    if unit:
                        metadata["column_units"][h] = unit
                        
                tables.append({
                    "page": 1,
                    "headers": headers,
                    "rows": df.astype(str).values.tolist(),
                    "sheet_name": sheet_name
                })
        else:
            df = pd.read_csv(file_path)
            headers = [str(x) for x in df.columns]
            for h in headers:
                unit = detect_unit(h)
                if unit:
                    metadata["column_units"][h] = unit
            
            tables.append({
                "page": 1,
                "headers": headers,
                "rows": df.astype(str).values.tolist(),
                "sheet_name": "csv_data"
            })
            
        return {
            "filename": file_path.split('/')[-1],
            "doc_type": "tabular_data",
            "pages": 1,
            "full_text": "",
            "tables": tables,
            "sections": [],
            "metadata": metadata
        }
    except Exception as e:
        print(f"Failed to parse tabular {file_path}: {e}", file=sys.stderr)
        return None
