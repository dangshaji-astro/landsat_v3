"""
Physics Engine - Slope Stability Calculator
Uses Infinite Slope Model (Mohr-Coulomb Criterion)
"""
import math
from typing import Dict, Optional


# Soil Property Database (Based on USDA classifications)
# Values from geotechnical engineering literature
SOIL_PROPERTIES = {
    "Clay": {
        "cohesion_kpa": 25,      # Cohesive strength
        "friction_angle": 15,     # Internal friction (degrees)
        "unit_weight": 18.5,      # kN/m³
        "porosity": 0.45,         # 45% pore space
        "saturated_capacity": 0.40  # Can hold 40% water
    },
    "Silty Clay": {
        "cohesion_kpa": 20,
        "friction_angle": 18,
        "unit_weight": 18.0,
        "porosity": 0.42,
        "saturated_capacity": 0.38
    },
    "Sandy Clay": {
        "cohesion_kpa": 15,
        "friction_angle": 22,
        "unit_weight": 19.0,
        "porosity": 0.38,
        "saturated_capacity": 0.32
    },
    "Clay Loam": {
        "cohesion_kpa": 18,
        "friction_angle": 20,
        "unit_weight": 17.5,
        "porosity": 0.40,
        "saturated_capacity": 0.35
    },
    "Silty Clay Loam": {
        "cohesion_kpa": 16,
        "friction_angle": 22,
        "unit_weight": 17.0,
        "porosity": 0.42,
        "saturated_capacity": 0.36
    },
    "Sandy Clay Loam": {
        "cohesion_kpa": 12,
        "friction_angle": 25,
        "unit_weight": 18.5,
        "porosity": 0.35,
        "saturated_capacity": 0.30
    },
    "Loam": {
        "cohesion_kpa": 10,
        "friction_angle": 28,
        "unit_weight": 17.0,
        "porosity": 0.40,
        "saturated_capacity": 0.32
    },
    "Silty Loam": {
        "cohesion_kpa": 8,
        "friction_angle": 26,
        "unit_weight": 16.5,
        "porosity": 0.43,
        "saturated_capacity": 0.34
    },
    "Sandy Loam": {
        "cohesion_kpa": 5,
        "friction_angle": 30,
        "unit_weight": 17.5,
        "porosity": 0.38,
        "saturated_capacity": 0.28
    },
    "Silt": {
        "cohesion_kpa": 6,
        "friction_angle": 24,
        "unit_weight": 16.0,
        "porosity": 0.45,
        "saturated_capacity": 0.38
    },
    "Loamy Sand": {
        "cohesion_kpa": 2,
        "friction_angle": 32,
        "unit_weight": 18.0,
        "porosity": 0.35,
        "saturated_capacity": 0.25
    },
    "Sand": {
        "cohesion_kpa": 0,
        "friction_angle": 35,
        "unit_weight": 18.5,
        "porosity": 0.30,
        "saturated_capacity": 0.22
    },
    # === KERALA-SPECIFIC ===
    "Laterite (Kerala)": {
        # Research-backed values from Kerala soil studies
        # Sources: Indian Geotechnical Journal, Kerala PWD reports
        "cohesion_kpa": 38.6,    # From field testing (igs.org.in)
        "friction_angle": 22.3,   # Measured for Kerala laterite
        "unit_weight": 17.5,      # Typical for porous laterite (15-30% porosity)
        "porosity": 0.22,         # Mid-range (15-30% water absorption)
        "saturated_capacity": 0.28  # Good drainage but retains some water
    },
    "Laterite": {
        # Alias for Kerala laterite (most common term)
        "cohesion_kpa": 38.6,
        "friction_angle": 22.3,
        "unit_weight": 17.5,
        "porosity": 0.22,
        "saturated_capacity": 0.28
    },
    "Unknown": {
        "cohesion_kpa": 10,
        "friction_angle": 25,
        "unit_weight": 17.5,
        "porosity": 0.40,
        "saturated_capacity": 0.30
    }
}


def get_soil_properties(soil_texture: str) -> Dict:
    """
    Retrieve engineering properties for a soil type
    """
    return SOIL_PROPERTIES.get(soil_texture, SOIL_PROPERTIES["Unknown"])


def estimate_saturation_from_rainfall(rain_7day_mm: float, soil_texture: str) -> float:
    """
    Estimate current soil saturation level from recent rainfall
    
    Args:
        rain_7day_mm: 7-day cumulative rainfall
        soil_texture: Soil type name
    
    Returns:
        Saturation ratio (0.0 to 1.0)
    """
    props = get_soil_properties(soil_texture)
    max_capacity_mm = props["saturated_capacity"] * 1000  # Convert to mm depth
    
    # Simplified model: assume 50% of rain infiltrates and accumulates
    effective_infiltration = rain_7day_mm * 0.5
    
    # Saturation ratio
    saturation = min(effective_infiltration / max_capacity_mm, 1.0)
    
    return saturation


def calculate_factor_of_safety(
    slope_degrees: float,
    soil_texture: str,
    saturation_ratio: float,
    depth_m: float = 2.0
) -> Dict:
    """
    Calculate Factor of Safety (FoS) using Infinite Slope Model
    
    FoS = (Cohesion + Normal_Stress * tan(Friction)) / Shear_Stress
    
    Args:
        slope_degrees: Slope angle in degrees
        soil_texture: Soil type
        saturation_ratio: Water saturation (0.0 = dry, 1.0 = fully saturated)
        depth_m: Depth of potential failure plane (meters)
    
    Returns:
        Dict with FoS, stability status, and component values
    """
    # Get soil properties
    props = get_soil_properties(soil_texture)
    cohesion = props["cohesion_kpa"]
    friction_angle = props["friction_angle"]
    unit_weight = props["unit_weight"]  # kN/m³
    
    # Convert slope to radians
    slope_rad = math.radians(slope_degrees)
    friction_rad = math.radians(friction_angle)
    
    # Calculate stresses
    # Normal stress on slope: σ = γ * z * cos²(β)
    normal_stress = unit_weight * depth_m * (math.cos(slope_rad) ** 2)
    
    # Shear stress: τ = γ * z * sin(β) * cos(β)
    shear_stress = unit_weight * depth_m * math.sin(slope_rad) * math.cos(slope_rad)
    
    # Pore water pressure (reduces effective stress)
    # u = saturation * γ_water * z * cos²(β)
    water_unit_weight = 9.81  # kN/m³
    pore_pressure = saturation_ratio * water_unit_weight * depth_m * (math.cos(slope_rad) ** 2)
    
    # Effective stress
    effective_stress = normal_stress - pore_pressure
    
    # Resisting force (Mohr-Coulomb)
    # τ_resist = c' + σ' * tan(φ')
    resisting_stress = cohesion + effective_stress * math.tan(friction_rad)
    
    # Factor of Safety
    if shear_stress > 0:
        fos = resisting_stress / shear_stress
    else:
        fos = 999  # Flat slope
    
    # Stability classification
    if fos < 1.0:
        stability = "UNSTABLE"
        risk_level = "CRITICAL"
    elif fos < 1.2:
        stability = "MARGINALLY STABLE"
        risk_level = "HIGH"
    elif fos < 1.5:
        stability = "STABLE"
        risk_level = "MEDIUM"
    else:
        stability = "VERY STABLE"
        risk_level = "LOW"
    
    return {
        "factor_of_safety": round(fos, 2),
        "stability": stability,
        "risk_level": risk_level,
        "components": {
            "cohesion_kpa": cohesion,
            "friction_angle_deg": friction_angle,
            "normal_stress_kpa": round(normal_stress, 2),
            "shear_stress_kpa": round(shear_stress, 2),
            "pore_pressure_kpa": round(pore_pressure, 2),
            "effective_stress_kpa": round(effective_stress, 2),
            "resisting_stress_kpa": round(resisting_stress, 2)
        }
    }


def simulate_future_rain_impact(
    current_fos: float,
    current_rain_mm: float,
    future_rain_rate_mm_per_day: float,
    soil_texture: str,
    slope_degrees: float,
    days_to_simulate: int = 5
) -> Dict:
    """
    Simulate how FoS changes if rain continues
    
    Returns:
        Dict with time-series FoS and critical day prediction
    """
    props = get_soil_properties(soil_texture)
    max_capacity_mm = props["saturated_capacity"] * 1000
    
    timeline = []
    critical_day = None
    
    for day in range(days_to_simulate + 1):
        # Cumulative rain
        total_rain = current_rain_mm + (future_rain_rate_mm_per_day * day)
        
        # Saturation
        saturation = estimate_saturation_from_rainfall(total_rain, soil_texture)
        
        # Calculate FoS for this scenario
        result = calculate_factor_of_safety(slope_degrees, soil_texture, saturation)
        
        timeline.append({
            "day": day,
            "cumulative_rain_mm": round(total_rain, 1),
            "saturation": round(saturation, 3),
            "fos": result["factor_of_safety"],
            "stability": result["stability"]
        })
        
        # Detect critical day (when FoS drops below 1.0)
        if critical_day is None and result["factor_of_safety"] < 1.0:
            critical_day = day
    
    return {
        "timeline": timeline,
        "critical_day": critical_day,
        "warning": f"Slope will become UNSTABLE in {critical_day} days" if critical_day else "Slope remains stable for the forecast period"
    }


if __name__ == "__main__":
    # Test the physics engine
    print("=== Physics Engine Test ===\n")
    
    # Scenario: Steep slope, clay soil, heavy rain
    slope = 35  # degrees
    soil = "Clay"
    rain_7day = 150  # mm
    
    print(f"Scenario: {slope} degree slope, {soil} soil, {rain_7day}mm rain\n")
    
    # Calculate saturation
    saturation = estimate_saturation_from_rainfall(rain_7day, soil)
    print(f"Estimated Saturation: {saturation*100:.1f}%\n")
    
    # Calculate FoS
    result = calculate_factor_of_safety(slope, soil, saturation)
    print(f"Factor of Safety: {result['factor_of_safety']}")
    print(f"Stability: {result['stability']}")
    print(f"Risk Level: {result['risk_level']}\n")
    
    # Print stress components
    print("Stress Analysis:")
    for key, value in result['components'].items():
        print(f"  {key}: {value}")
    
    # Future simulation
    print("\n=== Future Simulation (50mm/day rain) ===")
    forecast = simulate_future_rain_impact(
        current_fos=result['factor_of_safety'],
        current_rain_mm=rain_7day,
        future_rain_rate_mm_per_day=50,
        soil_texture=soil,
        slope_degrees=slope,
        days_to_simulate=5
    )
    
    print(f"WARNING: {forecast['warning']}\n")
    
    print("Timeline:")
    for entry in forecast['timeline']:
        print(f"  Day {entry['day']}: Rain={entry['cumulative_rain_mm']}mm, FoS={entry['fos']} ({entry['stability']})")
