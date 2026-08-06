
import sys
import os
import torch

print(f"Python: {sys.version}")
print(f"PyTorch: {torch.__version__}")
print(f"CUDA Available: {torch.cuda.is_available()}")
if torch.cuda.is_available():
    print(f"Device: {torch.cuda.get_device_name(0)}")

try:
    print("\n[1] Importing Libraries...")
    from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig
    from peft import PeftModel
    print("Success.")
except ImportError as e:
    print(f"FAILED: {e}")
    sys.exit(1)

MODEL_NAME = "TinyLlama/TinyLlama-1.1B-Chat-v1.0"
ADAPTER_PATH = "expert_model_v1"

print(f"\n[2] Checking Adapter Path: {os.path.abspath(ADAPTER_PATH)}")
if not os.path.exists(ADAPTER_PATH):
    print("FAILED: Adapter directory not found!")
    sys.exit(1)
print("Adapter found.")

print(f"\n[3] Attempting to Load Model (CPU-only first to test path/config)...")
try:
    # Minimal CPU load to verify files
    tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME, trust_remote_code=True)
    print("Tokenizer loaded.")
    
    # Try loading model - handling potential Windows bitsandbytes issues
    print("Loading Model...")
    model = AutoModelForCausalLM.from_pretrained(
        MODEL_NAME,
        device_map="cpu", # Force CPU for safety test
        trust_remote_code=True
    )
    print("Base Model loaded on CPU.")
    
    print("Loading Adapter...")
    model = PeftModel.from_pretrained(model, ADAPTER_PATH)
    print("Fine-Tuned Adapter loaded successfully!")
    
    print("\n[SUCCESS] The files are good. The issue might be GPU/Quantization config in app.")

except Exception as e:
    print(f"\n[CRITICAL ERROR] Loading failed:\n{e}")
    import traceback
    traceback.print_exc()
