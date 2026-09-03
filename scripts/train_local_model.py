import os
import json
import torch
from datasets import Dataset
from transformers import (
    AutoTokenizer, 
    AutoModelForSequenceClassification, 
    TrainingArguments, 
    Trainer,
    DataCollatorWithPadding
)
import evaluate
import numpy as np

def load_data(jsonl_path):
    print(f"Loading data from {jsonl_path}...")
    texts = []
    labels = []
    
    with open(jsonl_path, 'r', encoding='utf-8') as f:
        for i, line in enumerate(f):
            # Limit to 1000 for fast local training demo
            if i >= 1000:
                break
                
            record = json.loads(line)
            conversations = record.get("conversations", [])
            if len(conversations) < 3:
                continue
                
            narrative = conversations[1]["content"]
            assistant_response = conversations[2]["content"]
            
            try:
                parsed_response = json.loads(assistant_response)
                is_sif = parsed_response.get("is_sif_precursor", False)
                texts.append(narrative)
                labels.append(1 if is_sif else 0)
            except Exception:
                continue
                
    return Dataset.from_dict({"text": texts, "label": labels})

def compute_metrics(eval_pred):
    metric = evaluate.load("accuracy")
    logits, labels = eval_pred
    predictions = np.argmax(logits, axis=-1)
    return metric.compute(predictions=predictions, references=labels)

def train():
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    data_path = os.path.join(base_dir, "data", "fine_tuning", "bsee_training_data.jsonl")
    output_dir = os.path.join(base_dir, "models", "sif_distilbert")
    
    # 1. Load Data
    dataset = load_data(data_path)
    print(f"Loaded {len(dataset)} records.")
    
    # Split into train/eval
    dataset = dataset.train_test_split(test_size=0.1)
    
    # 2. Tokenizer
    model_name = "distilbert-base-uncased"
    tokenizer = AutoTokenizer.from_pretrained(model_name)
    
    def tokenize_function(examples):
        return tokenizer(examples["text"], truncation=True, max_length=128)
        
    tokenized_datasets = dataset.map(tokenize_function, batched=True)
    
    data_collator = DataCollatorWithPadding(tokenizer=tokenizer)
    
    # 3. Model
    print(f"Downloading {model_name}...")
    model = AutoModelForSequenceClassification.from_pretrained(
        model_name, num_labels=2
    )
    
    # 4. Training Arguments
    training_args = TrainingArguments(
        output_dir=output_dir,
        learning_rate=2e-5,
        per_device_train_batch_size=16,
        per_device_eval_batch_size=16,
        num_train_epochs=1,
        weight_decay=0.01,
        evaluation_strategy="epoch",
        save_strategy="epoch",
        load_best_model_at_end=True,
    )
    
    # 5. Trainer
    trainer = Trainer(
        model=model,
        args=training_args,
        train_dataset=tokenized_datasets["train"],
        eval_dataset=tokenized_datasets["test"],
        tokenizer=tokenizer,
        data_collator=data_collator,
        compute_metrics=compute_metrics,
    )
    
    # 6. Train
    print("Starting training loop...")
    trainer.train()
    
    # 7. Save
    print(f"Saving final model to {output_dir}...")
    trainer.save_model(output_dir)
    print("Training complete!")

if __name__ == "__main__":
    train()
