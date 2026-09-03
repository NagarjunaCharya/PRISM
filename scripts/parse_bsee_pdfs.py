import os
import glob
import fitz
import pandas as pd
import re

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
CSV_PATH = os.path.join(DATA_DIR, "cleaned", "osha_incidents.csv")

def clean_text(text):
    # Remove problematic characters like block elements, zero width spaces, etc.
    text = text.replace('\u2580', ' ')
    text = text.replace('\u2584', ' ')
    text = text.replace('\u2588', ' ')
    text = text.replace('\u200b', ' ')
    text = text.replace('\ufffd', ' ')
    
    # Remove excessive whitespace and newlines
    text = re.sub(r'\s+', ' ', text)
    return text.strip()

def parse_pdfs():
    print("Searching for PDFs in data directory...")
    pdf_files = glob.glob(os.path.join(DATA_DIR, "**", "*.pdf"), recursive=True)
    print(f"Found {len(pdf_files)} PDF files.")
    
    records = []
    
    for i, pdf_path in enumerate(pdf_files):
        filename = os.path.basename(pdf_path)
        print(f"[{i+1}/{len(pdf_files)}] Parsing {filename}...")
        
        try:
            doc = fitz.open(pdf_path)
            full_text = ""
            for page in doc:
                full_text += page.get_text() + " "
            
            cleaned = clean_text(full_text)
            
            # Since Nemotron might struggle with massive context windows (if some PDFs are 50 pages),
            # we'll truncate to the first 10,000 characters which usually contains the executive summary
            # and incident narrative in BSEE reports.
            if len(cleaned) > 10000:
                cleaned = cleaned[:10000] + "... (truncated)"
                
            if not cleaned.strip():
                continue
                
            # Create a mock record matching the OSHA dataset schema
            records.append({
                "ID": f"BSEE-{filename}",
                "UPA": "BSEE-OFFSHORE",
                "EventDate": "2024-01-01", # Placeholder
                "Employer": "Offshore Operator",
                "Address1": "Gulf of Mexico",
                "Address2": "",
                "City": "Offshore",
                "State": "OFFSHORE",
                "Zip": "00000",
                "Latitude": 28.0,
                "Longitude": -90.0,
                "Primary NAICS": "2111",
                "Hospitalized": 1.0,
                "Amputation": 0.0,
                "Loss of Eye": 0.0,
                "Inspection": filename,
                "Final Narrative": cleaned,
                "Nature": 999,
                "NatureTitle": "Offshore Incident",
                "Part of Body": 999,
                "Part of Body Title": "Unspecified",
                "Event": 999,
                "EventTitle": "Offshore Event",
                "Source": 999,
                "SourceTitle": "Offshore Source",
                "Secondary Source": 999,
                "Secondary Source Title": "Unspecified",
                "FederalState": "1"
            })
            
        except Exception as e:
            print(f"Failed to parse {filename}: {e}")
            
    if not records:
        print("No records extracted.")
        return
        
    print(f"Successfully extracted {len(records)} narratives. Prepending to {CSV_PATH}...")
    
    new_df = pd.DataFrame(records)
    
    # Read existing CSV
    existing_df = pd.read_csv(CSV_PATH, low_memory=False)
    
    # Ensure columns match exactly
    for col in existing_df.columns:
        if col not in new_df.columns:
            new_df[col] = pd.NA
            
    # Reorder columns to match
    new_df = new_df[existing_df.columns]
    
    # Concatenate with new_df on top
    combined_df = pd.concat([new_df, existing_df], ignore_index=True)
    
    # Save back to CSV
    combined_df.to_csv(CSV_PATH, index=False)
    print("Done! Restart the Uvicorn server to ingest these into the dashboard.")

if __name__ == "__main__":
    parse_pdfs()
