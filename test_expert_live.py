"""
Test if Expert AI actually loads and responds
"""
import sys
sys.path.insert(0, '.')

print("=" * 60)
print("TESTING EXPERT AI")
print("=" * 60)

from expert_agent import get_expert_analysis

# Test Data
data = {
    "terrain": {"slope_degrees": 25.0},
    "soil": {"texture": "Laterite"},
    "rainfall": {"7day_mm": 120.0}
}

fos = {"factor_of_safety": 0.85}

print("\n[TEST 1] General Risk Assessment")
response1 = get_expert_analysis(data, fos, user_question=None)
print(response1)

print("\n" + "=" * 60)
print("[TEST 2] Specific Question: 'Why is this area risky?'")
response2 = get_expert_analysis(data, fos, user_question="Why is this area risky?")
print(response2)

print("\n" + "=" * 60)
print("[TEST 3] Specific Question: 'Can I build here?'")
response3 = get_expert_analysis(data, fos, user_question="Can I build a house here?")
print(response3)

print("\n" + "=" * 60)
if "Error: AI Model is not loaded" in response1:
    print("❌ FAILED: Model did not load")
elif "Simulation" in response1:
    print("⚠️ WARNING: Still in simulation mode")
else:
    print("✅ SUCCESS: Real AI is responding!")
    if response1 == response2 == response3:
        print("⚠️ But responses are identical - training issue")
    else:
        print("✅ Responses are varied - working correctly!")
