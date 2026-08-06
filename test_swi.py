"""
Quick test to verify Soil Water Index (SWI) is working correctly.
Run from landsat_v2 folder: python test_swi.py
"""
from app.predictor import compute_swi, predict_risk

print("=" * 60)
print("SOIL WATER INDEX (SWI) VERIFICATION TEST")
print("=" * 60)

# ── Test 1: Same total rain, very different patterns ───────────
print("\n[TEST 1] Same rain7 total (70mm) — different patterns")

# Single burst then dry
burst = [70, 0, 0, 0, 0, 0, 0]
steady = [10, 10, 10, 10, 10, 10, 10]

swi_burst  = compute_swi(burst,  "Laterite")
swi_steady = compute_swi(steady, "Laterite")

print(f"  Single burst (70mm day1, dry rest): SWI={swi_burst['swi']}mm  Sat={swi_burst['saturation']*100:.1f}%")
print(f"  Steady 10mm/day for 7 days:         SWI={swi_steady['swi']}mm  Sat={swi_steady['saturation']*100:.1f}%")
print(f"  >> Expected: steady has HIGHER SWI (wetter soil): {'PASS ✅' if swi_steady['swi'] > swi_burst['swi'] else 'FAIL ❌'}")

# ── Test 2: Risk comparison ────────────────────────────────────
print("\n[TEST 2] Risk levels for the same zone (Wayanad-like: DEM=780m, slope=22°)")

r_burst  = predict_risk(780, 22, 70, history=burst,  soil_type="Laterite")
r_steady = predict_risk(780, 22, 70, history=steady, soil_type="Laterite")

print(f"  Burst pattern:  Risk={r_burst['risk_level']}   Prob={r_burst['probability']*100:.1f}%  Sat={r_burst.get('soil_saturation','N/A')}%")
print(f"  Steady pattern: Risk={r_steady['risk_level']}  Prob={r_steady['probability']*100:.1f}%  Sat={r_steady.get('soil_saturation','N/A')}%")
print(f"  >> Expected: steady is higher risk: {'PASS ✅' if r_steady['probability'] >= r_burst['probability'] else 'FAIL ❌'}")

# ── Test 3: Saturation ceiling ─────────────────────────────────
print("\n[TEST 3] Monsoon saturation (should cap at field capacity)")

monsoon = [80, 75, 90, 85, 70, 95, 88]  # ~583mm in 7 days — Kerala worst case
swi_max = compute_swi(monsoon, "Laterite")
print(f"  Heavy monsoon 7-day history: SWI={swi_max['swi']}mm  (field_capacity={swi_max['field_capacity']}mm)")
print(f"  Saturation: {swi_max['saturation']*100:.1f}%")
print(f"  >> Expected: SWI capped at 280mm: {'PASS ✅' if swi_max['swi'] <= 280 else 'FAIL ❌'}")

# ── Test 4: No history fallback ────────────────────────────────
print("\n[TEST 4] Fallback when no history (legacy rain7 mode)")
r_no_hist = predict_risk(780, 22, 70)
print(f"  No history: Risk={r_no_hist['risk_level']}  Prob={r_no_hist['probability']*100:.1f}%  SWI={'N/A (no history)'}")
print(f"  >> Expected: No 'swi' key in result: {'PASS ✅' if 'swi' not in r_no_hist else 'FAIL ❌'}")

print("\n" + "=" * 60)
print("Done! If all PASS, SWI is working correctly.")
print("=" * 60)
