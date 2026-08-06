"""
Test Kerala Laterite soil properties
"""
from physics_engine import calculate_factor_of_safety, estimate_saturation_from_rainfall

# Test scenario: Kerala slope with laterite soil
print("=== Kerala Laterite Test ===\n")

slope = 30  # degrees (typical Kerala hillslope)
soil = "Laterite"
rain_7day = 200  # mm (heavy monsoon)

print(f"Scenario: {slope} degree slope, Kerala {soil}, {rain_7day}mm rain\n")

# Calculate saturation
saturation = estimate_saturation_from_rainfall(rain_7day, soil)
print(f"Estimated Saturation: {saturation*100:.1f}%\n")

# Calculate FoS with Kerala-specific laterite properties
result = calculate_factor_of_safety(slope, soil, saturation)

print(f"Factor of Safety: {result['factor_of_safety']}")
print(f"Stability: {result['stability']}")
print(f"Risk Level: {result['risk_level']}\n")

print("Kerala Laterite Properties (Research-backed):")
print(f"  Cohesion: {result['components']['cohesion_kpa']} kPa")
print(f"  Friction Angle: {result['components']['friction_angle_deg']} degrees")
print(f"  Pore Pressure: {result['components']['pore_pressure_kpa']} kPa")
