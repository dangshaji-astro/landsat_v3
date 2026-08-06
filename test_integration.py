"""
Test Integration: Data Collector + Physics Engine
Demonstrates the complete Expert Analysis pipeline
"""
import json
from data_collector import collect_all_data
from physics_engine import (
    calculate_factor_of_safety,
    estimate_saturation_from_rainfall,
    simulate_future_rain_impact,
    get_soil_properties
)


def generate_expert_report(lat: float, lon: float):
    """
    Generate a complete Expert Geologist Report for a location
    
    This is what Model 2 will output when the user clicks "Ask Expert"
    """
    print(f"\n{'='*60}")
    print(f"EXPERT GEOLOGIST REPORT")
    print(f"Location: {lat}, {lon}")
    print(f"{'='*60}\n")
    
    # Step 1: Collect all data
    print("[1/3] Collecting multi-source data...")
    try:
        data = collect_all_data(lat, lon)
    except Exception as e:
        print(f"Error: {e}")
        return
    
    # Step 2: Run physics calculations
    print("[2/3] Running slope stability analysis...")
    
    slope = data['terrain']['slope_degrees']
    soil_texture = data['soil']['texture']
    rain_7day = data['rainfall']['7day_mm']
    
    # Calculate saturation
    saturation = estimate_saturation_from_rainfall(rain_7day, soil_texture)
    
    # Calculate Factor of Safety
    fos_result = calculate_factor_of_safety(
        slope_degrees=slope,
        soil_texture=soil_texture,
        saturation_ratio=saturation
    )
    
    # Future simulation
    future_sim = simulate_future_rain_impact(
        current_fos=fos_result['factor_of_safety'],
        current_rain_mm=rain_7day,
        future_rain_rate_mm_per_day=50,  # Conservative assumption
        soil_texture=soil_texture,
        slope_degrees=slope,
        days_to_simulate=3
    )
    
    # Step 3: Generate Report
    print("[3/3] Generating expert analysis...\n")
    
    print("-" * 60)
    print("LOCATION OVERVIEW")
    print("-" * 60)
    print(f"  Taluk: {data['location']['taluk']}")
    print(f"  Elevation: {data['terrain']['elevation_m']}m")
    print(f"  Slope: {slope} degrees")
    print(f"  Land Cover: {data['land_cover']}")
    
    print("\n" + "-" * 60)
    print("SOIL ANALYSIS")
    print("-" * 60)
    soil_props = get_soil_properties(soil_texture)
    print(f"  Texture: {soil_texture}")
    print(f"  Cohesion: {soil_props['cohesion_kpa']} kPa")
    print(f"  Friction Angle: {soil_props['friction_angle']} degrees")
    print(f"  Saturation Level: {saturation*100:.1f}%")
    print(f"  GEE Status: {data['soil']['moisture_status']}")
    
    print("\n" + "-" * 60)
    print("VEGETATION HEALTH (5-Year Trend)")
    print("-" * 60)
    ndvi_change = data['vegetation']['ndvi_change_5yr']
    degradation = data['vegetation']['degradation_flag']
    if degradation:
        print(f"  WARNING: {ndvi_change}% vegetation LOSS detected!")
        print(f"  Deforestation or land clearing is increasing risk.")
    else:
        print(f"  Change: {ndvi_change}%")
        print(f"  Status: Normal vegetation cover maintained.")
    
    print("\n" + "-" * 60)
    print("METEOROLOGICAL DATA")
    print("-" * 60)
    print(f"  7-Day Rainfall: {rain_7day}mm")
    
    print("\n" + "-" * 60)
    print("SLOPE STABILITY ANALYSIS (Physics)")
    print("-" * 60)
    print(f"  Factor of Safety (FoS): {fos_result['factor_of_safety']}")
    print(f"  Stability Classification: {fos_result['stability']}")
    print(f"  Risk Level: {fos_result['risk_level']}")
    
    print("\n  Stress Components:")
    for key, value in fos_result['components'].items():
        print(f"    {key}: {value}")
    
    print("\n" + "-" * 60)
    print("PREDICTIVE SIMULATION (50mm/day rain)")
    print("-" * 60)
    print(f"  {future_sim['warning']}")
    print("\n  Forecast Timeline:")
    for entry in future_sim['timeline']:
        status_icon = "[!]" if entry['fos'] < 1.2 else "[ ]"
        print(f"    {status_icon} Day {entry['day']}: FoS={entry['fos']} ({entry['stability']})")
    
    print("\n" + "-" * 60)
    print("EXPERT RECOMMENDATION")
    print("-" * 60)
    
    # Generate recommendation based on all factors
    if fos_result['factor_of_safety'] < 1.0:
        print("  CRITICAL: Immediate evacuation recommended.")
        print("  The slope is currently UNSTABLE and failure is imminent.")
    elif fos_result['factor_of_safety'] < 1.2:
        print("  HIGH ALERT: Monitor closely. Prepare for evacuation.")
        print("  Slope is marginally stable. Any additional rain is dangerous.")
    elif degradation and fos_result['factor_of_safety'] < 1.5:
        print("  CAUTION: Vegetation loss has weakened the slope.")
        print("  Enforce reforestation and avoid further land clearing.")
    elif future_sim['critical_day']:
        print(f"  WARNING: Slope will become critical in {future_sim['critical_day']} days.")
        print("  Issue early warning if rain forecast continues.")
    else:
        print("  STABLE: Current conditions are within safe limits.")
        print("  Continue routine monitoring.")
    
    print("\n" + "=" * 60 + "\n")
    
    # Return structured data (for API)
    return {
        "location": data['location'],
        "factor_of_safety": fos_result['factor_of_safety'],
        "stability": fos_result['stability'],
        "risk_level": fos_result['risk_level'],
        "degradation_detected": degradation,
        "critical_day": future_sim['critical_day'],
        "recommendation": "EVACUATE" if fos_result['factor_of_safety'] < 1.0 else "MONITOR"
    }


if __name__ == "__main__":
    # Test with a Wayanad location
    report = generate_expert_report(11.6, 76.1)
    
    # Print JSON output (for API integration)
    print("\nAPI Output (JSON):")
    print(json.dumps(report, indent=2))
