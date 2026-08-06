"""
Dataset Generator for Expert Geologist Model
Converts extracted knowledge into Instruction-Tuning Dataset (JSONL)
"""
import json
import random
from typing import List, Dict

# Templates to vary the user questions (Data Augmentation)
USER_PROMPTS = [
    "Assess the landslide risk for this location based on the given data.",
    "Here is the data for a slope in Kerala. Is it safe?",
    "Analyze the stability of this terrain.",
    "What is the expert verdict on this potential landslide site?",
    "Review these soil and rain conditions and predict the outcome.",
    "As a geologist, evaluate the risk factor here."
]

def generate_synthetic_samples(knowledge: Dict, num_samples: int = 500) -> List[Dict]:
    """
    Generate synthetic Q&A pairs mixing real extracted knowledge with physics templates
    """
    samples = []
    
    causes = knowledge.get("causes", [])
    recommendations = knowledge.get("recommendations", [])
    
    print(f"Generating {num_samples} synthetic training samples...")
    
    for _ in range(num_samples):
        # 1. Create a Synthetic Scenario
        slope = random.randint(20, 60)
        rain = random.choice([50, 100, 200, 300, 400])
        soil = random.choice(["Laterite", "Clay", "Sandy Loam", "Forest Soil"])
        fos = round(random.uniform(0.5, 1.8), 2)
        
        # 2. Determine Ground Truth
        is_safe = fos > 1.2
        risk_level = "LOW" if fos > 1.5 else "HIGH" if fos < 1.0 else "MEDIUM"
        
        # 3. Pick a "Real World" reason if available
        real_cause = random.choice(causes) if causes else "Heavy rainfall caused soil saturation."
        real_rec = random.choice(recommendations) if recommendations else "Evacuate immediately."
        
        # 4. Construct the Input (The Prompt)
        prompt = f"""
Location Data:
- Slope: {slope} degrees
- Soil Type: {soil} (Kerala)
- Rainfall (7-day): {rain}mm
- Factor of Safety (Physics Calc): {fos}
"""
        user_q = random.choice(USER_PROMPTS)
        input_text = f"{user_q}\n{prompt}"
        
        # 5. Construct the Output (The Expert Response)
        if is_safe:
            response = f"""
**Expert Assessment: STABLE**

Based on the physics analysis (FoS: {fos}), this slope is currently stable. although {rain}mm of rain has fallen, the {soil} soil has maintained sufficient cohesion.
Recommendation: Continue routine monitoring. No immediate threat detected.
"""
        else:
            response = f"""
**Expert Assessment: DANGER - {risk_level} RISK**

The calculated Factor of Safety is {fos} (Unstable).
Analysis:
1. **Trigger**: Extreme rainfall of {rain}mm has likely saturated the {soil}.
2. **Vulnerability**: The slope angle of {slope} degrees exceeds the critical angle for saturated laterite.
3. **Observation**: Similar to historical cases where "{real_cause}".

**Verdict**: The slope is failing. {real_rec}
"""
        
        # Add to dataset
        samples.append({
            "instruction": input_text.strip(),
            "output": response.strip()
        })
    
    return samples


if __name__ == "__main__":
    # Load raw extracted knowledge
    try:
        with open("extracted_knowledge.json", "r", encoding="utf-8") as f:
            raw_knowledge = json.load(f)
    except FileNotFoundError:
        print("extracted_knowledge.json not found! Using dummy data for testing.")
        raw_knowledge = {"causes": ["heavy rain"], "recommendations": ["run"]}

    # Generate dataset
    dataset = generate_synthetic_samples(raw_knowledge, num_samples=500)
    
    # Save as JSONL (Standard format for Fine-Tuning)
    output_path = "landsat_expert_training_data.jsonl"
    with open(output_path, "w", encoding="utf-8") as f:
        for entry in dataset:
            f.write(json.dumps(entry) + "\n")
            
    print(f"\n[OK] Created {len(dataset)} training examples in {output_path}")
