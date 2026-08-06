"""
Export Trained LoRA Model to Ollama (GGUF Format)
-------------------------------------------------
After running the training notebook (Start_Training.ipynb),
this script converts the LoRA adapter to a GGUF model for Ollama.

Prerequisites:
1. Run training in Colab and download `lora_model` folder
2. Install llama-cpp-python: pip install llama-cpp-python
3. Have Ollama installed locally

Usage:
    python export_to_ollama.py
"""
import os
import subprocess

# Configuration
LORA_MODEL_PATH = "./lora_model"  # From Colab training
MERGED_MODEL_PATH = "./expert_geologist_merged"
GGUF_OUTPUT = "./expert_geologist.gguf"
OLLAMA_MODEL_NAME = "llama3-geologist"

def merge_lora_to_base():
    """Merge LoRA adapters with base model."""
    print("[1/3] Merging LoRA adapters with base model...")
    
    # This requires unsloth to be installed
    try:
        from unsloth import FastLanguageModel
        
        model, tokenizer = FastLanguageModel.from_pretrained(
            model_name=LORA_MODEL_PATH,
            max_seq_length=2048,
            load_in_4bit=False,  # We need full precision for export
        )
        
        # Save merged model
        model.save_pretrained_merged(MERGED_MODEL_PATH, tokenizer, save_method="merged_16bit")
        print(f"   -> Merged model saved to {MERGED_MODEL_PATH}")
        
    except ImportError:
        print("   [ERROR] unsloth not installed. Install with: pip install unsloth")
        print("   [ALT] You can also merge using the Colab notebook before download.")
        return False
    
    return True

def convert_to_gguf():
    """Convert merged model to GGUF format."""
    print("[2/3] Converting to GGUF format...")
    
    # Requires llama.cpp's convert script
    convert_script = "llama.cpp/convert.py"  # Adjust path as needed
    
    if not os.path.exists(convert_script):
        print("   [NOTE] llama.cpp not found locally.")
        print("   Run: git clone https://github.com/ggerganov/llama.cpp")
        print("   Then: python llama.cpp/convert-hf-to-gguf.py {} --outfile {}".format(
            MERGED_MODEL_PATH, GGUF_OUTPUT
        ))
        return False
    
    result = subprocess.run([
        "python", convert_script,
        MERGED_MODEL_PATH,
        "--outfile", GGUF_OUTPUT,
        "--outtype", "q4_k_m"  # 4-bit quantization for smaller size
    ])
    
    return result.returncode == 0

def create_ollama_model():
    """Create Ollama model from GGUF."""
    print("[3/3] Creating Ollama model...")
    
    # Create Modelfile
    modelfile_content = f"""FROM {GGUF_OUTPUT}

PARAMETER temperature 0.7
PARAMETER top_p 0.9

SYSTEM \"\"\"
You are an Expert Engineering Geologist with 20 years of experience specializing in 
Kerala's Western Ghats. You assess landslide risk using the Infinite Slope Model and 
interpret Factor of Safety calculations. Always be professional, safety-oriented, and 
explain technical concepts clearly.
\"\"\"
"""
    
    with open("Modelfile", "w") as f:
        f.write(modelfile_content)
    
    print(f"   -> Modelfile created")
    
    # Create the Ollama model
    print(f"   -> Running: ollama create {OLLAMA_MODEL_NAME} -f Modelfile")
    result = subprocess.run(["ollama", "create", OLLAMA_MODEL_NAME, "-f", "Modelfile"])
    
    if result.returncode == 0:
        print(f"\n[SUCCESS] Ollama model '{OLLAMA_MODEL_NAME}' created!")
        print(f"   Test with: ollama run {OLLAMA_MODEL_NAME}")
    else:
        print("[ERROR] Failed to create Ollama model")
    
    return result.returncode == 0


if __name__ == "__main__":
    print("=" * 60)
    print("Export LoRA Model to Ollama")
    print("=" * 60)
    
    # Check if LoRA model exists
    if not os.path.exists(LORA_MODEL_PATH):
        print(f"[ERROR] LoRA model not found at {LORA_MODEL_PATH}")
        print("        Please run training first (Start_Training.ipynb in Colab)")
        exit(1)
    
    # Run pipeline
    if merge_lora_to_base():
        if convert_to_gguf():
            create_ollama_model()
        else:
            print("\n[INFO] Manual GGUF conversion required. See instructions above.")
    
    print("\nDone.")
