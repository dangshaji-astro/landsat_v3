"""
Test the trained LoRA model with a sample geological query.
"""
import torch
from transformers import AutoModelForCausalLM, AutoTokenizer
from peft import PeftModel

# Paths
BASE_MODEL = "TinyLlama/TinyLlama-1.1B-Chat-v1.0"
LORA_PATH = "./expert_model_lora"

print("🔄 Loading base model...")
base_model = AutoModelForCausalLM.from_pretrained(
    BASE_MODEL,
    torch_dtype=torch.float16,
    device_map="auto"
)

print("🔄 Loading LoRA adapter...")
model = PeftModel.from_pretrained(base_model, LORA_PATH)
tokenizer = AutoTokenizer.from_pretrained(LORA_PATH)

print("✅ Model loaded! Testing...\n")

# Test prompt
prompt = """### Question:
What are the primary factors that contribute to landslide risk in Kerala's Western Ghats?

### Answer:
"""

inputs = tokenizer(prompt, return_tensors="pt").to(model.device)

print("🤔 Generating response...")
with torch.no_grad():
    outputs = model.generate(
        **inputs,
        max_new_tokens=150,
        do_sample=False,  # Greedy decoding - more stable
        pad_token_id=tokenizer.eos_token_id,
        eos_token_id=tokenizer.eos_token_id
    )

response = tokenizer.decode(outputs[0], skip_special_tokens=True)
print("\n" + "="*60)
print("GEOLOGIST MODEL RESPONSE:")
print("="*60)
print(response)
print("="*60)
