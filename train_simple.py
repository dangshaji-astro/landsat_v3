"""
Simple Local LLM Trainer (NO bitsandbytes - pure fp16)
Works on Windows with any NVIDIA GPU
"""
import torch
from transformers import (
    AutoModelForCausalLM,
    AutoTokenizer,
    TrainingArguments,
    Trainer,
    DataCollatorForLanguageModeling
)
from peft import LoraConfig, get_peft_model, TaskType
from datasets import load_dataset
import os

# === CONFIGURATION ===
# Using a TINY model that fits in 4GB VRAM
MODEL_NAME = "TinyLlama/TinyLlama-1.1B-Chat-v1.0"
MAX_SEQ_LENGTH = 512  # Short sequences to save memory

def train():
    print(f"🚀 Initializing Training for {MODEL_NAME}...")
    print(f"   GPU: {torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'CPU'}")
    print(f"   VRAM: {torch.cuda.get_device_properties(0).total_memory / 1024**3:.1f} GB")
    
    # 1. Load Model (fp16, no quantization)
    print("\n📦 Loading Model (this takes ~1 min)...")
    model = AutoModelForCausalLM.from_pretrained(
        MODEL_NAME,
        torch_dtype=torch.float16,
        device_map="auto",
        trust_remote_code=True,
        low_cpu_mem_usage=True
    )
    model.config.use_cache = False
    
    # 2. Load Tokenizer
    tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME, trust_remote_code=True)
    tokenizer.pad_token = tokenizer.eos_token
    tokenizer.padding_side = "right"

    # 3. LoRA Config (lightweight fine-tuning)
    print("\n⚙️ Configuring LoRA...")
    peft_config = LoraConfig(
        task_type=TaskType.CAUSAL_LM,
        r=8,  # Low rank for memory efficiency
        lora_alpha=16,
        lora_dropout=0.05,
        target_modules=["q_proj", "v_proj"],  # Only tune attention
        inference_mode=False
    )
    model = get_peft_model(model, peft_config)
    model.print_trainable_parameters()

    # 4. Load Dataset
    print("\n📂 Loading Dataset...")
    dataset = load_dataset("json", data_files="landsat_expert_training_data.jsonl", split="train")
    
    def format_example(example):
        text = f"### Instruction:\n{example['instruction']}\n\n### Response:\n{example['output']}"
        tokens = tokenizer(
            text,
            truncation=True,
            max_length=MAX_SEQ_LENGTH,
            padding="max_length"
        )
        tokens["labels"] = tokens["input_ids"].copy()
        return tokens
    
    dataset = dataset.map(format_example, remove_columns=dataset.column_names)
    
    # 5. Training Arguments (conservative for 4GB VRAM)
    training_args = TrainingArguments(
        output_dir="./expert_model_checkpoints",
        num_train_epochs=1,
        per_device_train_batch_size=1,  # Minimal batch size
        gradient_accumulation_steps=8,  # Effective batch = 8
        learning_rate=2e-4,
        bf16=True,  # Use bf16 instead of fp16 (avoids gradient scaling issues)
        fp16=False,
        logging_steps=10,
        save_steps=100,
        save_total_limit=2,
        warmup_steps=5,  # Use steps instead of ratio
        optim="adamw_torch",  # Standard optimizer
        report_to="none",
        max_grad_norm=1.0,
    )

    # 6. Data Collator
    data_collator = DataCollatorForLanguageModeling(
        tokenizer=tokenizer,
        mlm=False
    )

    # 7. Trainer
    trainer = Trainer(
        model=model,
        args=training_args,
        train_dataset=dataset,
        data_collator=data_collator,
    )

    # 8. Train!
    print("\n🏋️ Starting Training...")
    print("   (This will take 5-15 minutes depending on your GPU)")
    trainer.train()

    # 9. Save
    print("\n💾 Saving Model...")
    model.save_pretrained("./expert_model_lora")
    tokenizer.save_pretrained("./expert_model_lora")
    print("\n✅ Done! Model saved to ./expert_model_lora")

if __name__ == "__main__":
    train()
