import os
import json
import pandas as pd
import sys

# Ensure app is in path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from app.sif_detector import detector

def generate_nemo_dataset(input_csv: str, output_jsonl: str, max_records: int = 5000):
    print(f"Reading {input_csv}...")
    try:
        df = pd.read_csv(input_csv, encoding="ISO-8859-1")
    except Exception as e:
        print(f"Error reading CSV: {e}")
        return

    # Look for the description column
    text_col = None
    for col in df.columns:
        if "description" in col.lower() or "narrative" in col.lower():
            text_col = col
            break
            
    if not text_col:
        print("Could not find a description/narrative column.")
        return

    print(f"Found narrative column: {text_col}")
    
    # Create output dir
    os.makedirs(os.path.dirname(output_jsonl), exist_ok=True)
    
    processed = 0
    with open(output_jsonl, 'w', encoding='utf-8') as f:
        for idx, row in df.iterrows():
            if processed >= max_records:
                break
                
            narrative = str(row[text_col]).strip()
            if not narrative or len(narrative) < 20 or str(narrative).lower() == "nan":
                continue
                
            # Use our SIF detector to generate "pseudo-labels" for distillation
            res = detector.detect(narrative)
            
            # Format the desired JSON response
            expected_output = {
                "is_sif_precursor": res.is_sif_precursor,
                "overall_score": float(res.overall_score) / 100.0,
                "top_category": res.top_category.replace("_", " ") if res.top_category else None,
                "extracted_entities": res.entities,
                "severity_level": res.severity_level
            }
            
            # NeMo Automodel SteerLM / SFT format (System, User, Assistant)
            record = {
                "conversations": [
                    {
                        "role": "system",
                        "content": "You are an OSHA Safety Expert AI. Analyze the incident narrative and detect if it is a Serious Injury or Fatality (SIF) precursor. Respond purely in JSON."
                    },
                    {
                        "role": "user",
                        "content": narrative
                    },
                    {
                        "role": "assistant",
                        "content": json.dumps(expected_output)
                    }
                ]
            }
            
            f.write(json.dumps(record) + "\n")
            processed += 1
            
            if processed % 1000 == 0:
                print(f"Processed {processed} records...")
                
    print(f"Successfully generated {processed} fine-tuning records at {output_jsonl}")

if __name__ == "__main__":
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    input_file = os.path.join(base_dir, "data", "cleaned", "osha_incidents.csv")
    output_file = os.path.join(base_dir, "data", "fine_tuning", "bsee_training_data.jsonl")
    
    generate_nemo_dataset(input_file, output_file, max_records=5000)
