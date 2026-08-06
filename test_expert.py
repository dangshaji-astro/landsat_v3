"""
Test the Expert Geologist Agent
"""
from expert_agent import get_expert_analysis

# Mock Data (Simulating a risky location)
mock_data = {
    "terrain": {"slope_degrees": 35},
    "soil": {"texture": "Laterite"},
    "rainfall": {"7day_mm": 150}
}

mock_fos = {
    "factor_of_safety": 0.85 # Risky!
}

print("Testing Expert Agent...")
response = get_expert_analysis(mock_data, mock_fos)

print("\n--- EXPERT ANALYSIS ---")
print(response)
print("-----------------------")
