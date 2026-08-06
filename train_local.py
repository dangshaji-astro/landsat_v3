"""
Local LLM Trainer for Windows (RTX 3050 - 4GB VRAM)
Uses bitsandbytes (windows) + PEFT + Transformers
"""
import torch
from transformers import (
    AutoModelForCausalLM,
    AutoTokenizer,
    BitsAndBytesConfig,
    TrainingArguments
)
from peft import (
    LoraConfig,
    get_peft_model,
    prepare_model_for_kbit_training
)
from trl import SFTTrainer
from datasets import load_dataset
import os

# === CONFIGURATION ===
MODEL_NAME = "Unbabel/TowerBase-7B-v0.1"  # Or "TinyLlama/TinyLlama-1.1B-Chat-v1.0" for super speed
# NOTE: Llama-3-8B might be too big for 4GB even with QLoRA.
# Suggesting TinyLlama-1.1B for guaranteed 4GB fit, or try Llama-3-8B and see if it OOMs.
TARGET_MODEL = "TinyLlama/TinyLlama-1.1B-Chat-v1.0" 

MAX_SEQ_LENGTH = 1024

def train_local():
    print(f"🚀 Initializing Training for {TARGET_MODEL}...")
    
    # 1. Quantization Config (4-bit)
    bnb_config = BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_quant_type="nf4",
        bnb_4bit_compute_dtype=torch.float16,
        bnb_4bit_use_double_quant=True,
    )

    # 2. Load Model
    print("📦 Loading Model...")
    model = AutoModelForCausalLM.from_pretrained(
        TARGET_MODEL,
        quantization_config=bnb_config,
        device_map="auto",
        trust_remote_code=True
    )
    model.config.use_cache = False
    model.config.pretraining_tp = 1
    
    # Prepare for k-bit training
    model = prepare_model_for_kbit_training(model)

    # 3. Load Tokenizer
    tokenizer = AutoTokenizer.from_pretrained(TARGET_MODEL, trust_remote_code=True)
    tokenizer.pad_token = tokenizer.eos_token
    tokenizer.padding_side = "right"

    # 4. LoRA Config
    peft_config = LoraConfig(
        lora_alpha=16,
        lora_dropout=0.1,
        r=8,
        bias="none",
        task_type="CAUSAL_LM",
        target_modules=["q_proj", "v_proj"] # TinyLlama modules
    )
    
    model = get_peft_model(model, peft_config)
    model.print_trainable_parameters()

    # 5. Load Dataset
    print("\n📂 Loading Dataset...")
    dataset = load_dataset("json", data_files="landsat_expert_training_data.jsonl", split="train")

    def format_prompt(example):
        output_texts = []
        for i in range(len(example['instruction'])):
            text = f"### Prediction:\n{example['instruction'][i]}\n\n### Analysis:\n{example['output'][i]}"
            output_texts.append(text)
        return output_texts

    # 6. Training Arguments
    training_args = TrainingArguments(
        output_dir="expert_model_checkpoints",
        num_train_epochs=1,
        per_device_train_batch_size=1,
        gradient_accumulation_steps=4,
        optim="paged_adamw_32bit",
        save_steps=50,
        logging_steps=5,
        learning_rate=2e-4,
        weight_decay=0.001,
        fp16=True,
        bf16=False,
        max_grad_norm=0.3,
        max_steps=100,
        warmup_ratio=0.03,
        group_by_length=True,
        lr_scheduler_type="constant",
    )

    # 7. Trainer
    trainer = SFTTrainer(
        model=model,
        train_dataset=dataset,
        peft_config=peft_config,
        max_seq_length=MAX_SEQ_LENGTH,
        tokenizer=tokenizer,
        args=training_args,
        packing=False,
        formatting_func=format_prompt,
    )

    print("\n🏋️ Starting Training...")
    trainer.train()

    # 8. Save
    print("\n💾 Saving Model...")
    trainer.model.save_pretrained("expert_model_v1")
    print("✅ Done!")

if __name__ == "__main__":
    train_local()
