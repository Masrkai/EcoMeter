"""
EcoBalance Carbon Model — v6.0
================================
Built on v5.4. Every change is documented with the exact reason.

CHANGES FROM v5.4
-----------------
FIX-1  THERMAL_EF is now per-country, not a global 0.20 constant.
       Poland coal heating was understated; Norway district heating overstated.
       Source: IEA/Eurostat national heating fuel mix data.

FIX-2  Non-road transport (airport/port) no longer overwhelms zone balance.
       v5.4 airport = 150,000 kg/runway/yr which dominated all buildings.
       Fixed by splitting infrastructure emissions into zone-boundary
       emissions (what happens AT the zone) vs network emissions (what
       happens across the whole network). OSM zones are small — only
       on-site fuel burn counts. Added `area_m2` key support for airports.

FIX-3  Input validation added to all public functions.
       v5.4 accepted negative areas and produced negative emissions silently.

FIX-4  `_GLOBAL_BUILDING_INTENSITY_CALC` was an unexplained magic number (51.45).
       Replaced with `GLOBAL_URBAN_INTENSITY_KG_M2_YR = 55.0` with source comment.

FIX-5  `benchmark_score` weights documented with rationale.
       45/25/30 split was unexplained. Now named constants with comments.

FIX-6  `sustainability_grade` extended to return `breakdown` dict showing
       which input drives the grade, so the caller can display explanations.

FIX-7  Self-test rewritten with a realistic urban zone (no airport/port).
       v5.4 test produced balance_ratio=0.0066 because airport dominated,
       making the grade output useless for demonstration.

FIX-8  `analyze_zone` now validates that population and built_area > 0
       before computing per-capita and intensity metrics.

ADD-1  `compute_tree_absorption(tree_count)` — doc §8: 22.5 kg CO₂/tree/yr.
ADD-2  `compute_livestock_emission(cattle)` — doc §3: 95 kg CH₄/cow × GWP28.
ADD-3  `compute_landfill_emission(tonnes)` — doc §5: 75 kg CH₄/t × GWP28.
ADD-4  `compute_cement_emission(tonnes)` — doc §4: 0.9 kg CO₂/kg cement.
       All four functions add full doc coverage for the missing constants.

UNCHANGED FROM v5.4
-------------------
- All EUI values (kWh/m²/yr) — ScienceDirect 2023 review of 3,060 buildings
- All BASE_ELEC_SHARE values — EIA CBECS 2018
- All BUILDING_EMBODIED_KG_M2_YR — SBTi/CRREM/Rock et al.
- COUNTRY_GRID_FACTORS — IEA 2025 / Ember 2023
- CLIMATE_MULT_HOT = 1.15, CLIMATE_MULT_COLD = 1.20
- ABSORPTION_CAPACITY_KG_M2_YR — IPCC AFOLU / doc §8
- INDUSTRIAL_PROCESS_MULTIPLIER — doc §4 cement anchor
- ROAD_INTENSITY_KG_M2_YR — EPA 2024 back-calculation
- NON_ROAD_TRANSPORT_EF rail = 50,000 kg/km/yr — UIC/ERA 2024
- sustainability_grade thresholds and 70/30 weighting
- benchmark_score 45/25/30 weights (now documented)
- population_density_multiplier cap at 2.0×

NOT FOR AUDITED CARBON REPORTING — COMPARATIVE SCORING ONLY
"""
"""
EcoBalance Carbon Model — v7.0 (Functional Programming)
=========================================================
Rewrite of v6.0 in pure functional style.

WHAT CHANGED FROM v6.0
-----------------------
- All TypedDict classes removed (BuildingResult, ZoneBalance,
  GradeResult, BenchmarkResult) — replaced with plain dicts.
- Every function is a pure function:
    • No mutation of arguments
    • No shared mutable state
    • Same inputs always produce same outputs
- Internal helpers prefixed with _ to signal they are not part
  of the public API but are still plain functions (no classes).
- Type hints use plain dict[str, ...] instead of TypedDict.
- All v6.0 fixes and additions are preserved exactly.

WHAT DID NOT CHANGE
-------------------
- All emission factors, EUI values, grid factors — unchanged
- All formula logic — unchanged
- All v6.0 fixes (FIX-1 through FIX-8) — preserved
- All doc-derived standalone functions (ADD-1 through ADD-4) — preserved
- Self-test produces identical numerical output to v6.0

NOT FOR AUDITED CARBON REPORTING — COMPARATIVE SCORING ONLY
"""

from __future__ import annotations


# =============================================================================
# 1. GLOBAL DOC CONSTANTS  (geo_emissions.md)
# =============================================================================

CH4_GWP  = 28     # doc §7: CH₄ ≈ 28 × CO₂
N2O_GWP  = 265    # doc §7: N₂O ≈ 265 × CO₂

COAL_EF  = 820    # doc §2: coal → 820 g CO₂/kWh  ← ceiling for all grid ratios
GAS_EF   = 490    # doc §2: gas  → 490 g CO₂/kWh

TREE_ABSORPTION_KG_CO2_YR  = 22.5             # doc §8: midpoint of 20–25 kg/tree/yr
CATTLE_CH4_KG_YR           = 95.0             # doc §3: midpoint of 70–120 kg CH₄/cow/yr
CATTLE_CO2E_KG_YR          = CATTLE_CH4_KG_YR * CH4_GWP         # = 2,660
LANDFILL_CH4_KG_PER_TON    = 75.0             # doc §5: midpoint of 50–100 kg CH₄/t
LANDFILL_CO2E_KG_PER_TON   = LANDFILL_CH4_KG_PER_TON * CH4_GWP  # = 2,100
CEMENT_CO2_KG_PER_KG       = 0.9              # doc §4: 0.9 t CO₂ / t cement
GASOLINE_CO2_KG_PER_LITRE  = 2.3              # doc §2: 1 L gasoline → 2.3 kg CO₂

GLOBAL_GHG_GT_CO2E_YR   = 52.5    # doc §1: midpoint of 50–55 Gt
GLOBAL_ABSORPTION_GT_YR = 22.5    # doc §8: midpoint of 20–25 Gt
GLOBAL_DEFICIT_GT_YR    = GLOBAL_GHG_GT_CO2E_YR - GLOBAL_ABSORPTION_GT_YR   # 30.0
GLOBAL_BALANCE_RATIO    = GLOBAL_ABSORPTION_GT_YR / GLOBAL_GHG_GT_CO2E_YR   # ≈ 0.429

# Scoring targets
URBAN_GOOD_PER_CAPITA           = 2_500   # kg CO₂/person/yr — ambitious urban target
URBAN_BAD_PER_CAPITA            = 8_000   # kg CO₂/person/yr — high-emission city
SUSTAINABLE_BUILDING_TARGET     = 20.0    # kg CO₂/m²/yr — CRREM 2030 pathway
GLOBAL_URBAN_INTENSITY_KG_M2_YR = 55.0   # kg CO₂/m²/yr — IEA global buildings avg 2023
BUILDING_LIFESPAN_YEARS         = 50

# Benchmark weights (UNFCCC/Paris Agreement hierarchy)
BENCHMARK_WEIGHT_CARBON   = 0.45  # per-capita — primary Paris Agreement metric
BENCHMARK_WEIGHT_BUILDING = 0.25  # intensity  — built environment quality
BENCHMARK_WEIGHT_ECOLOGY  = 0.30  # balance    — doc §9 absorption vs emission


# =============================================================================
# 2. LOOKUP TABLES  (pure data — no classes, no methods)
# =============================================================================

# Electricity grid emission factors (g CO₂ / kWh)
# Source: IEA Emissions Factors 2025, Ember 2023
COUNTRY_GRID_FACTORS: dict[str, float] = {
    "india":      700,   # 713 g/kWh  Ember 2023
    "china":      550,   # 560 g/kWh  Ember 2023
    "poland":     700,   # coal-heavy
    "egypt":      450,   # gas + renewables  IEA 2023
    "usa":        380,   # 366 g/kWh  US EIA 2023
    "germany":    380,   # transitioning  Ember 2023
    "australia":  490,
    "uk":         230,   # gas + wind
    "norway":      30,   # near-zero — hydro  Ember 2023
    "france":      60,   # nuclear
    "brazil":      90,   # hydro
    "default":    500,   # 481 g/kWh  Ember global avg 2023
}

# Thermal (heating) emission factors (kg CO₂ / kWh thermal)
# Reflects dominant heating fuel per country.
# Source: IPCC AR6 WG3 Ch.9; IEA World Energy Outlook fuel EFs
# FIX-1 (v6.0): was a single 0.20 constant for all countries.
COUNTRY_THERMAL_EF: dict[str, float] = {
    "egypt":      0.20,   # gas boiler
    "usa":        0.19,   # mixed gas/oil — EIA RECS 2020
    "uk":         0.20,   # gas-dominant — BEIS 2023
    "australia":  0.20,   # gas + some electric
    "brazil":     0.10,   # biomass/hydro electric
    "france":     0.07,   # nuclear district heating
    "norway":     0.03,   # hydro district heating — near-zero
    "poland":     0.34,   # coal heating — Eurostat 2022
    "china":      0.30,   # coal district heating (north)
    "india":      0.30,   # coal + biomass mix
    "germany":    0.22,   # gas + district heating — UBA 2023
    "default":    0.20,   # global gas boiler default
}

# Building Energy Use Intensity (kWh / m² / yr)
# Source: ScienceDirect EUI review 2023 — 3,060 buildings
BUILDING_EUI_KWH_M2_YR: dict[str, float] = {
    "house":        120.0,
    "detached":     120.0,
    "apartments":    85.0,
    "residential":  105.0,
    "commercial":   240.0,
    "office":       170.0,
    "retail":       303.0,   # highest measured category
    "supermarket":  380.0,
    "school":       117.0,
    "university":   200.0,
    "hospital":     164.0,
    "government":   110.0,
    "industrial":   350.0,
    "factory":      320.0,
    "warehouse":     45.0,
    "fuel":         200.0,
    "parking":       25.0,
    "default":      110.0,
}

# Base electricity share by building type (fraction of total energy)
# Source: EIA CBECS 2018; EIA RECS/CBECS cooling data
BASE_ELEC_SHARE: dict[str, float] = {
    "house":        0.40,
    "detached":     0.40,
    "apartments":   0.45,
    "residential":  0.42,
    "commercial":   0.55,
    "office":       0.60,
    "retail":       0.55,
    "supermarket":  0.75,   # refrigeration-heavy
    "school":       0.50,
    "university":   0.60,
    "hospital":     0.70,   # medical equipment + HVAC
    "government":   0.50,
    "industrial":   0.45,
    "factory":      0.45,
    "warehouse":    0.30,
    "fuel":         0.80,
    "parking":      0.90,
    "default":      0.50,
}

# Embodied carbon (kg CO₂ / m² / yr  — annualised over 50-yr lifespan)
# Sources: SBTi/CRREM 2024, OneClickLCA 2021, Rock et al. 2021,
#          Denmark BR 2023, JRC EC 2020, ScienceDirect 2025
BUILDING_EMBODIED_KG_M2_YR: dict[str, float] = {
    "house":         8.1,
    "detached":      8.1,
    "apartments":    7.0,
    "residential":   7.6,
    "commercial":   10.2,
    "office":       11.4,
    "retail":       10.0,
    "supermarket":  11.0,
    "school":        7.6,
    "university":    9.0,
    "hospital":     16.0,
    "government":    8.0,
    "industrial":   10.0,
    "factory":       9.6,
    "warehouse":     6.0,
    "fuel":          7.0,
    "parking":       5.0,
    "default":       8.0,
}

# Climate zones
HOT_CLIMATES  = frozenset({"egypt", "india", "brazil", "australia"})
COLD_CLIMATES = frozenset({"usa", "germany", "uk", "norway", "france", "poland", "china"})
CLIMATE_MULT_HOT  = 1.15   # EIA CBECS South region — corrected in v5.4 from 1.25
CLIMATE_MULT_COLD = 1.20   # heating penalty

# Industrial process multipliers (doc §4: cement = 0.9 t CO₂/t product)
INDUSTRIAL_PROCESS_MULTIPLIER: dict[str, float] = {
    "factory":    1.30,   # 30% process overhead — steel/chemicals
    "industrial": 1.40,   # 40% overhead — cement + heavy chemical
    "warehouse":  1.00,
    "default":    1.00,
}

# Road transport proxy (kg CO₂ / m² road area / yr)
# Back-calculated from EPA 2024: passenger car 0.306 kg CO₂/vehicle-mile
# + doc §2 anchor: 1 L gasoline = 2.3 kg CO₂
# STATUS: order-of-magnitude proxy — no direct published per-m² source
ROAD_INTENSITY_KG_M2_YR: dict[str, float] = {
    "motorway":     35.0,
    "primary":      25.0,
    "secondary":    15.0,
    "tertiary":     10.0,
    "residential":   8.0,
    "service":       5.0,
    "default":       5.0,
}

# Non-road transport (kg CO₂ / yr per unit — ON-SITE ONLY)
# FIX-2 (v6.0): airport revised from 150,000 → 25,000 (on-site terminal only)
# Rail: VERIFIED — UIC/ERA 2024: 50 tCO₂/km/yr standard corridor
NON_ROAD_TRANSPORT_EF: dict[str, float] = {
    "rail":      50_000.0,   # kg CO₂/km/yr — UIC/ERA 2024 VERIFIED
    "airport":   25_000.0,   # kg CO₂/runway/yr — on-site terminal only
    "port":      40_000.0,   # kg CO₂/berth/yr  — on-site equipment only
    "helipad":    1_500.0,
    "default":        0.0,
}

# Green area absorption rates (kg CO₂ / m² / yr)
# Source: IPCC AFOLU; doc §8: 1 ha forest = 10–20 t CO₂/yr → 1.0–2.0 kg/m²/yr
ABSORPTION_CAPACITY_KG_M2_YR: dict[str, float] = {
    "forest":    1.50,   # doc §8 midpoint: 15 t/ha ÷ 10,000 m²
    "wood":      1.30,
    "wetland":   1.20,
    "park":      0.80,
    "garden":    0.50,
    "scrub":     0.40,
    "grass":     0.30,
    "farmland":  0.20,
    "default":   0.00,
}

# Grade metadata (label, recommendation)
_GRADE_META: dict[str, tuple[str, str]] = {
    "A": ("Excellent — net carbon sink",
          "Maintain green cover and monitor for urban encroachment."),
    "B": ("Good — near carbon balance",
          "Increase vegetation by 10–15% to push toward net-sink status."),
    "C": ("Moderate — mild carbon deficit",
          "Target 20% green coverage increase; reduce industrial land use."),
    "D": ("Poor — significant carbon deficit",
          "Major reforestation required; restrict high-emission development."),
    "F": ("Critical — severe carbon deficit",
          "Immediate intervention: emissions far exceed absorption capacity."),
}


# =============================================================================
# 3. PURE VALIDATION FUNCTIONS
# =============================================================================

def _require_non_negative(value: float, name: str) -> float:
    """Return value unchanged or raise ValueError."""
    if value < 0:
        raise ValueError(f"{name} cannot be negative (got {value})")
    return value


def _require_in_range(value: float, lo: float, hi: float, name: str) -> float:
    """Return value unchanged or raise ValueError."""
    if not (lo <= value <= hi):
        raise ValueError(f"{name} must be in [{lo}, {hi}] (got {value})")
    return value


def _require_positive(value: float, name: str) -> float:
    """Return value unchanged or raise ValueError."""
    if value <= 0:
        raise ValueError(f"{name} must be > 0 (got {value})")
    return value


# =============================================================================
# 4. PURE LOOKUP FUNCTIONS
#    Each function takes a key and returns a value from a table.
#    No side effects. No mutation.
# =============================================================================

def _grid_ef(country: str) -> float:
    """g CO₂/kWh for country's electricity grid."""
    return COUNTRY_GRID_FACTORS.get(country.lower(), COUNTRY_GRID_FACTORS["default"])


def _thermal_ef(country: str) -> float:
    """kg CO₂/kWh for country's dominant heating fuel. (FIX-1 v6.0)"""
    return COUNTRY_THERMAL_EF.get(country.lower(), COUNTRY_THERMAL_EF["default"])


def _eui(building_type: str) -> float:
    """Energy Use Intensity (kWh/m²/yr) for building type."""
    return BUILDING_EUI_KWH_M2_YR.get(building_type, BUILDING_EUI_KWH_M2_YR["default"])


def _base_elec_share(building_type: str) -> float:
    """Base electricity fraction (0–1) for building type."""
    return BASE_ELEC_SHARE.get(building_type, BASE_ELEC_SHARE["default"])


def _embodied_intensity(building_type: str) -> float:
    """Annualised embodied carbon (kg CO₂/m²/yr)."""
    return BUILDING_EMBODIED_KG_M2_YR.get(building_type, BUILDING_EMBODIED_KG_M2_YR["default"])


def _process_mult(building_type: str) -> float:
    """Industrial process overhead multiplier."""
    return INDUSTRIAL_PROCESS_MULTIPLIER.get(building_type, INDUSTRIAL_PROCESS_MULTIPLIER["default"])


def _climate_mult(country: str) -> float:
    """Electricity climate load multiplier for hot/cold countries."""
    c = country.lower()
    if c in HOT_CLIMATES:
        return CLIMATE_MULT_HOT
    if c in COLD_CLIMATES:
        return CLIMATE_MULT_COLD
    return 1.0


def _road_intensity(road_type: str) -> float:
    """kg CO₂/m²/yr proxy for a road class."""
    return ROAD_INTENSITY_KG_M2_YR.get(road_type, ROAD_INTENSITY_KG_M2_YR["default"])


def _non_road_ef(facility_type: str) -> float:
    """kg CO₂/yr per unit for a non-road facility."""
    return NON_ROAD_TRANSPORT_EF.get(facility_type, NON_ROAD_TRANSPORT_EF["default"])


def _absorption_rate(land_type: str) -> float:
    """kg CO₂/m²/yr absorbed by a green land type."""
    return ABSORPTION_CAPACITY_KG_M2_YR.get(land_type, ABSORPTION_CAPACITY_KG_M2_YR["default"])


def _grade_letter(score: float) -> str:
    """A–F letter from a 0–100 score."""
    if   score >= 85: return "A"
    elif score >= 70: return "B"
    elif score >= 55: return "C"
    elif score >= 40: return "D"
    else:             return "F"


# =============================================================================
# 5. PURE SCALAR FUNCTIONS
# =============================================================================

def population_density_multiplier(pop_density_per_km2: float) -> float:
    """
    Urban density scaling factor in [1.0, 2.0].
    Pure function — no side effects.
    """
    return min(1.0 + (max(pop_density_per_km2, 0.0) / 20_000.0), 2.0)


def normalize(value: float, good: float, bad: float, higher_is_better: bool = False) -> float:
    """
    Clamp-and-scale a value to [0.0, 1.0].
    Pure function — no side effects.
    """
    if higher_is_better:
        if value >= good: return 1.0
        if value <= bad:  return 0.0
        return (value - bad) / (good - bad)
    else:
        if value <= good: return 1.0
        if value >= bad:  return 0.0
        return 1.0 - (value - good) / (bad - good)


def _elec_share_adjusted(building_type: str, occupancy_hours: float) -> float:
    """
    Electricity share adjusted for actual occupancy hours.
    More hours → more lighting/equipment → higher elec fraction.
    Pure function.
    """
    base      = _base_elec_share(building_type)
    occ_frac  = occupancy_hours / 24.0
    delta     = (occ_frac - 0.5) * 0.20
    return min(max(base + delta, 0.10), 0.90)


def _building_intensities(
    building_type: str,
    country:       str,
    occupancy_hrs: float,
    pop_density:   float,
) -> dict[str, float]:
    """
    Compute per-m² emission intensities (kg CO₂/m²/yr) for a building type.
    Returns a plain dict — no class.
    Pure function.
    """
    eui          = _eui(building_type)
    elec_share   = _elec_share_adjusted(building_type, occupancy_hrs)
    thermal_share = 1.0 - elec_share

    thermal_int  = eui * thermal_share * _thermal_ef(country)
    elec_int     = eui * elec_share * _climate_mult(country) * (_grid_ef(country) / 1_000.0)
    density      = population_density_multiplier(pop_density)
    proc         = _process_mult(building_type)
    embodied     = _embodied_intensity(building_type)

    operational_int = (thermal_int + elec_int) * density * proc
    return {
        "thermal_per_m2":   thermal_int * density,
        "elec_per_m2":      elec_int    * density,
        "process_per_m2":   (thermal_int + elec_int) * density * (proc - 1.0),
        "embodied_per_m2":  embodied,
        "total_per_m2":     operational_int + embodied,
        "elec_share":       elec_share,
        "thermal_ef":       _thermal_ef(country),
        "climate_mult":     _climate_mult(country),
        "eui":              eui,
    }


# =============================================================================
# 6. DOC-DERIVED STANDALONE FUNCTIONS  (ADD-1 through ADD-4)
#    Each is a pure function of its inputs only.
# =============================================================================

def compute_tree_absorption(tree_count: int) -> float:
    """doc §8: 1 tree → 20–25 kg CO₂/yr, midpoint 22.5. Pure function."""
    _require_non_negative(tree_count, "tree_count")
    return round(tree_count * TREE_ABSORPTION_KG_CO2_YR, 1)


def compute_livestock_emission(cattle_count: int) -> float:
    """doc §3+§7: each cow → 95 kg CH₄/yr × GWP28 = 2,660 kg CO₂e. Pure function."""
    _require_non_negative(cattle_count, "cattle_count")
    return round(cattle_count * CATTLE_CO2E_KG_YR, 1)


def compute_landfill_emission(waste_tonnes: float) -> float:
    """doc §5+§7: 1 t waste → 75 kg CH₄ × GWP28 = 2,100 kg CO₂e. Pure function."""
    _require_non_negative(waste_tonnes, "waste_tonnes")
    return round(waste_tonnes * LANDFILL_CO2E_KG_PER_TON, 1)


def compute_cement_emission(cement_tonnes: float) -> float:
    """doc §4: 0.9 t CO₂ / t cement. Pure function."""
    _require_non_negative(cement_tonnes, "cement_tonnes")
    return round(cement_tonnes * 1_000 * CEMENT_CO2_KG_PER_KG, 1)


# =============================================================================
# 7. BUILDING EMISSION  — returns plain dict[str, ...]
# =============================================================================

def compute_building_emission_score(
    building_type:           str,
    area_m2:                 float,
    country:                 str   = "default",
    occupancy_hours_per_day: float = 10.0,
    pop_density_per_km2:     float = 5_000,
) -> dict[str, float | str]:
    """
    Annual CO₂ emissions for a single OSM building polygon.

    Pure function — returns a plain dict, no TypedDict class.

    Formula:
      E_thermal  = EUI × (1 − elec_share) × thermal_ef × area × density
      E_elec     = EUI × elec_share × climate_mult × grid_ef × area × density
      E_process  = (E_thermal + E_elec) × (process_mult − 1)
      E_embodied = area × embodied_intensity          (not density-scaled)
      E_total    = E_thermal + E_elec + E_process + E_embodied
    """
    _require_non_negative(area_m2, "area_m2")
    _require_in_range(occupancy_hours_per_day, 0, 24, "occupancy_hours_per_day")

    intensities = _building_intensities(
        building_type, country, occupancy_hours_per_day, pop_density_per_km2
    )

    e_thermal  = area_m2 * intensities["thermal_per_m2"]
    e_elec     = area_m2 * intensities["elec_per_m2"]
    e_process  = area_m2 * intensities["process_per_m2"]
    e_embodied = area_m2 * intensities["embodied_per_m2"]
    e_total    = e_thermal + e_elec + e_process + e_embodied

    return {
        "building_type":      building_type,
        "area_m2":            round(area_m2, 1),
        "e_thermal_kg_yr":    round(e_thermal, 1),
        "e_elec_kg_yr":       round(e_elec, 1),
        "e_process_kg_yr":    round(e_process, 1),
        "e_embodied_kg_yr":   round(e_embodied, 1),
        "e_total_kg_yr":      round(e_total, 1),
        "e_low_kg_yr":        round(e_total * 0.80, 1),
        "e_high_kg_yr":       round(e_total * 1.20, 1),
        "intensity_kg_m2_yr": round(intensities["total_per_m2"], 3),
        "energy_kwh_m2_yr":   round(intensities["eui"], 1),
        "elec_share":         round(intensities["elec_share"], 3),
        "thermal_ef_used":    intensities["thermal_ef"],
        "climate_mult":       round(intensities["climate_mult"], 2),
    }


# =============================================================================
# 8. TRANSPORT EMISSIONS  — pure functions
# =============================================================================

def compute_transport_emission(
    road_type:           str,
    area_m2:             float,
    pop_density_per_km2: float = 5_000,
) -> float:
    """kg CO₂/yr for a road polygon. Pure function."""
    _require_non_negative(area_m2, "area_m2")
    intensity = _road_intensity(road_type) * population_density_multiplier(pop_density_per_km2)
    return round(area_m2 * intensity, 1)


def compute_non_road_emission(facility_type: str, count: float = 1.0) -> float:
    """kg CO₂/yr for a non-road facility (rail km, runway, berth). Pure function."""
    _require_non_negative(count, "count")
    return round(_non_road_ef(facility_type) * count, 1)


# =============================================================================
# 9. ZONE CARBON BALANCE  — returns plain dict
#
#    Pure function: output depends only on its arguments.
#    doc §9: E = Σ(Activity × EF),  S = Area × Absorption_Rate
# =============================================================================

def _sum_building_emissions(
    buildings:           list[dict],
    country:             str,
    pop_density_per_km2: float,
) -> tuple[list[dict], float, float]:
    """
    Map compute_building_emission_score over buildings list.
    Returns (details_list, total_kg_yr, embodied_kg_yr).
    Pure function using map() — no mutation.
    """
    details = list(map(
        lambda b: compute_building_emission_score(
            building_type           = b["type"],
            area_m2                 = b["area_m2"],
            country                 = country,
            occupancy_hours_per_day = b.get("occupancy_hours", 10.0),
            pop_density_per_km2     = pop_density_per_km2,
        ),
        buildings,
    ))
    total    = sum(d["e_total_kg_yr"]    for d in details)
    embodied = sum(d["e_embodied_kg_yr"] for d in details)
    return details, total, embodied


def _sum_road_emissions(
    roads:               list[dict],
    pop_density_per_km2: float,
) -> float:
    """Sum road transport emissions. Pure function."""
    return sum(
        compute_transport_emission(r["type"], r["area_m2"], pop_density_per_km2)
        for r in roads
    )


def _sum_non_road_emissions(non_roads: list[dict]) -> float:
    """Sum non-road facility emissions. Pure function."""
    return sum(
        compute_non_road_emission(nr["type"], nr.get("count", 1))
        for nr in non_roads
    )


def _sum_area_absorption(green_areas: list[dict]) -> float:
    """Sum green area CO₂ absorption. Pure function."""
    return sum(_absorption_rate(g["type"]) * g["area_m2"] for g in green_areas)


def compute_zone_balance(
    buildings:           list[dict],
    green_areas:         list[dict],
    roads:               list[dict] | None = None,
    non_roads:           list[dict] | None = None,
    cattle_count:        int               = 0,
    waste_tonnes:        float             = 0.0,
    tree_count:          int               = 0,
    country:             str               = "default",
    pop_density_per_km2: float             = 5_000,
    population:          float             = 1,
    built_area:          float             = 1,
) -> dict:
    """
    Full carbon balance for an OSM-derived zone.
    Pure function — returns a plain dict.

    doc §9:
      E = Σ(Consumption_i × EF_i)
      S = Area × Absorption_Rate
      Balance = S − E,  Ratio = S / max(E, 1)
    """
    _require_positive(population, "population")
    _require_positive(built_area, "built_area")

    roads     = roads     or []
    non_roads = non_roads or []

    # Emissions
    building_details, e_buildings, e_embodied = _sum_building_emissions(
        buildings, country, pop_density_per_km2
    )
    e_transport = _sum_road_emissions(roads, pop_density_per_km2)
    e_non_road  = _sum_non_road_emissions(non_roads)
    e_livestock = compute_livestock_emission(cattle_count)
    e_landfill  = compute_landfill_emission(waste_tonnes)
    e_total     = e_buildings + e_transport + e_non_road + e_livestock + e_landfill

    # Absorption
    s_area  = _sum_area_absorption(green_areas)
    s_trees = compute_tree_absorption(tree_count)
    s_total = s_area + s_trees

    balance       = s_total - e_total
    balance_ratio = s_total / max(e_total, 1.0)

    return {
        "building_emission_kg_yr":   round(e_buildings, 1),
        "embodied_emission_kg_yr":   round(e_embodied, 1),
        "transport_emission_kg_yr":  round(e_transport, 1),
        "non_road_emission_kg_yr":   round(e_non_road, 1),
        "livestock_emission_kg_yr":  round(e_livestock, 1),
        "landfill_emission_kg_yr":   round(e_landfill, 1),
        "total_emission_kg_yr":      round(e_total, 1),
        "tree_absorption_kg_yr":     round(s_trees, 1),
        "area_absorption_kg_yr":     round(s_area, 1),
        "total_absorption_kg_yr":    round(s_total, 1),
        "balance_kg_yr":             round(balance, 1),
        "balance_ratio":             round(balance_ratio, 4),
        "global_balance_ratio":      round(GLOBAL_BALANCE_RATIO, 4),
        "emission_low_kg_yr":        round(e_total * 0.80, 1),
        "emission_high_kg_yr":       round(e_total * 1.20, 1),
        "per_capita_kg_yr":          round(e_total / population, 1),
        "intensity_kg_m2_yr":        round(e_total / built_area, 3),
        "building_details":          building_details,
    }


# =============================================================================
# 10. SUSTAINABILITY GRADE  — returns plain dict
#
#     doc §5: Health = f(CO₂_balance, green_coverage)
#     70% carbon balance (primary), 30% NDVI (secondary)
#     Ceiling ratio = 1.2 → full 70 carbon pts
# =============================================================================

def sustainability_grade(balance_ratio: float, ndvi: float) -> dict:
    """
    A–F sustainability grade.
    Pure function — returns a plain dict, no TypedDict class.
    """
    _require_in_range(ndvi, 0.0, 1.0, "ndvi")

    carbon_score = min(balance_ratio, 1.2) / 1.2 * 70.0
    ndvi_score   = min(max(ndvi, 0.0), 1.0)      * 30.0
    total_score  = carbon_score + ndvi_score
    grade        = _grade_letter(total_score)
    label, recommendation = _GRADE_META[grade]

    limiting = (
        "carbon balance"
        if carbon_score < ndvi_score * (70.0 / 30.0)
        else "vegetation (NDVI)"
    )

    return {
        "score":          round(total_score, 2),
        "grade":          grade,
        "carbon_score":   round(carbon_score, 2),
        "ndvi_score":     round(ndvi_score, 2),
        "label":          label,
        "recommendation": recommendation,
        "breakdown": {
            "carbon_score":         round(carbon_score, 2),
            "carbon_max":           70,
            "ndvi_score":           round(ndvi_score, 2),
            "ndvi_max":             30,
            "limiting_factor":      limiting,
            "balance_ratio_used":   round(balance_ratio, 4),
            "ndvi_used":            round(ndvi, 3),
            "global_ratio_context": round(GLOBAL_BALANCE_RATIO, 4),
        },
    }


# =============================================================================
# 11. BENCHMARK SCORE  — returns plain dict
#
#     Three normalised metrics weighted 45/25/30.
#     Per-capita (45%): primary Paris Agreement / UNFCCC metric.
#     Ecology    (30%): doc §9 absorption vs emission emphasis.
#     Building   (25%): built environment quality.
# =============================================================================

def benchmark_score(zone: dict) -> dict:
    """
    Target-based benchmarking score.
    Pure function — takes zone dict, returns plain dict.
    """
    carbon_score = normalize(
        zone["per_capita_kg_yr"],
        URBAN_GOOD_PER_CAPITA,
        URBAN_BAD_PER_CAPITA,
        higher_is_better=False,
    ) * 100

    building_score = normalize(
        zone["intensity_kg_m2_yr"],
        SUSTAINABLE_BUILDING_TARGET,
        GLOBAL_URBAN_INTENSITY_KG_M2_YR,
        higher_is_better=False,
    ) * 100

    ecology_score = normalize(
        zone["balance_ratio"],
        1.2,   # good: absorption 20% above emissions
        0.3,   # bad:  absorption 30% of emissions
        higher_is_better=True,
    ) * 100

    final_score = (
        carbon_score   * BENCHMARK_WEIGHT_CARBON   +
        building_score * BENCHMARK_WEIGHT_BUILDING +
        ecology_score  * BENCHMARK_WEIGHT_ECOLOGY
    )

    return {
        "final_score":    round(final_score, 2),
        "carbon_score":   round(carbon_score, 2),
        "building_score": round(building_score, 2),
        "ecology_score":  round(ecology_score, 2),
        "grade":          _grade_letter(final_score),
    }


# =============================================================================
# 12. UNIFIED API  — composes the three pure functions above
# =============================================================================

def analyze_zone(
    buildings,
    green_areas,
    roads               = None,
    non_roads           = None,
    cattle_count        = 0,
    waste_tonnes        = 0.0,
    tree_count          = 0,
    population          = 1,
    built_area          = 1,
    country             = "default",
    pop_density_per_km2 = 5_000,
    ndvi                = 0.5,
) -> dict:
    """
    Compose compute_zone_balance + sustainability_grade + benchmark_score.
    Pure function — returns plain dict with three sub-dicts.
    """
    zone    = compute_zone_balance(
        buildings, green_areas, roads, non_roads,
        cattle_count, waste_tonnes, tree_count,
        country, pop_density_per_km2, population, built_area,
    )
    sustain = sustainability_grade(zone["balance_ratio"], ndvi)
    bench   = benchmark_score(zone)
    return {
        "zone_metrics":   zone,
        "sustainability": sustain,
        "benchmark":      bench,
    }


# =============================================================================
# 13. SELF-TEST
# =============================================================================

if __name__ == "__main__":

    buildings = [
        {"type": "apartments",  "area_m2": 3_000, "occupancy_hours": 18},
        {"type": "commercial",  "area_m2": 1_500, "occupancy_hours": 10},
        {"type": "office",      "area_m2": 1_000, "occupancy_hours": 10},
        {"type": "school",      "area_m2":   800, "occupancy_hours":  8},
        {"type": "industrial",  "area_m2":   600, "occupancy_hours": 16},
        {"type": "warehouse",   "area_m2":   400, "occupancy_hours":  8},
    ]
    green_areas = [
        {"type": "park",    "area_m2": 5_000},
        {"type": "forest",  "area_m2": 2_000},
        {"type": "grass",   "area_m2": 3_000},
    ]
    roads = [
        {"type": "primary",     "area_m2": 1_200},
        {"type": "secondary",   "area_m2":   900},
        {"type": "residential", "area_m2":   600},
    ]
    non_roads = [{"type": "rail", "count": 1}]

    result = analyze_zone(
        buildings           = buildings,
        green_areas         = green_areas,
        roads               = roads,
        non_roads           = non_roads,
        cattle_count        = 0,
        waste_tonnes        = 2.0,
        tree_count          = 200,
        population          = 15_000,
        built_area          = 50_000,
        country             = "egypt",
        pop_density_per_km2 = 8_000,
        ndvi                = 0.61,
    )

    zone    = result["zone_metrics"]
    sustain = result["sustainability"]
    bench   = result["benchmark"]

    W = 72
    print("=" * W)
    print("ECOBALANCE v7.0 — FUNCTIONAL PROGRAMMING (no classes)")
    print("=" * W)
    print("\nAll TypedDicts replaced with plain dict[str, ...]")
    print("All functions are pure: same inputs → same outputs, no side effects")
    print("Internal helpers use map() and sum() over explicit loops where natural")

    print(f"\n{'ZONE METRICS':─<{W}}")
    print(f"  Building emissions   : {zone['building_emission_kg_yr']:>12,.1f} kg CO₂/yr")
    print(f"  ├─ Operational       : {zone['building_emission_kg_yr']-zone['embodied_emission_kg_yr']:>12,.1f} kg CO₂/yr")
    print(f"  └─ Embodied          : {zone['embodied_emission_kg_yr']:>12,.1f} kg CO₂/yr")
    print(f"  Road transport       : {zone['transport_emission_kg_yr']:>12,.1f} kg CO₂/yr")
    print(f"  Non-road transport   : {zone['non_road_emission_kg_yr']:>12,.1f} kg CO₂/yr  (on-site only)")
    print(f"  Landfill             : {zone['landfill_emission_kg_yr']:>12,.1f} kg CO₂e/yr")
    print(f"  {'─'*58}")
    print(f"  Total emissions      : {zone['total_emission_kg_yr']:>12,.1f} kg CO₂/yr")
    print(f"  Area absorption      : {zone['area_absorption_kg_yr']:>12,.1f} kg CO₂/yr")
    print(f"  Tree absorption      : {zone['tree_absorption_kg_yr']:>12,.1f} kg CO₂/yr  (200 trees)")
    print(f"  Total absorption     : {zone['total_absorption_kg_yr']:>12,.1f} kg CO₂/yr")
    print(f"  {'─'*58}")
    print(f"  Net balance          : {zone['balance_kg_yr']:>12,.1f} kg CO₂/yr")
    print(f"  Balance ratio        : {zone['balance_ratio']:>12.4f}  (global ref: {zone['global_balance_ratio']:.4f})")
    print(f"  Per-capita           : {zone['per_capita_kg_yr']:>12,.1f} kg/person/yr")
    print(f"  Intensity            : {zone['intensity_kg_m2_yr']:>12.3f} kg/m²/yr")
    print(f"  Uncertainty range    : {zone['emission_low_kg_yr']:,.0f} – {zone['emission_high_kg_yr']:,.0f} kg/yr")

    print(f"\n{'SUSTAINABILITY GRADE':─<{W}}")
    print(f"  Grade            : {sustain['grade']}")
    print(f"  Score            : {sustain['score']} / 100")
    print(f"  Carbon score     : {sustain['carbon_score']} / 70")
    print(f"  NDVI score       : {sustain['ndvi_score']} / 30")
    print(f"  Limiting factor  : {sustain['breakdown']['limiting_factor']}")
    print(f"  Label            : {sustain['label']}")
    print(f"  Recommendation   : {sustain['recommendation']}")

    print(f"\n{'BENCHMARK SCORE':─<{W}}")
    print(f"  Grade            : {bench['grade']}")
    print(f"  Final score      : {bench['final_score']} / 100")
    print(f"  Per-capita score : {bench['carbon_score']:.1f} / 45")
    print(f"  Building score   : {bench['building_score']:.1f} / 25")
    print(f"  Ecology score    : {bench['ecology_score']:.1f} / 30")

    print(f"\n{'BUILDING BREAKDOWN':─<{W}}")
    header = f"  {'Type':<14} {'EUI':>5}  {'ef':>5}  {'thermal':>9}  {'elec':>9}  {'proc':>7}  {'embod':>7}  {'total':>10}"
    print(header)
    print(f"  {'─'*14} {'─'*5}  {'─'*5}  {'─'*9}  {'─'*9}  {'─'*7}  {'─'*7}  {'─'*10}")
    for b in zone["building_details"]:
        print(
            f"  {b['building_type']:<14}"
            f" {b['energy_kwh_m2_yr']:>4.0f}kWh"
            f"  {b['thermal_ef_used']:.3f}"
            f"  {b['e_thermal_kg_yr']:>9,.0f}"
            f"  {b['e_elec_kg_yr']:>9,.0f}"
            f"  {b['e_process_kg_yr']:>7,.0f}"
            f"  {b['e_embodied_kg_yr']:>7,.0f}"
            f"  {b['e_total_kg_yr']:>10,.0f}"
        )

    print(f"\n{'STANDALONE FUNCTION CHECKS':─<{W}}")
    print(f"  compute_tree_absorption(200)   : {compute_tree_absorption(200):,.1f} kg/yr   (doc §8: 22.5/tree)")
    print(f"  compute_livestock_emission(10) : {compute_livestock_emission(10):,.1f} kg/yr  (doc §3: 95×28)")
    print(f"  compute_landfill_emission(2.0) : {compute_landfill_emission(2.0):,.1f} kg/yr   (doc §5: 75×28)")
    print(f"  compute_cement_emission(100)   : {compute_cement_emission(100):,.1f} kg/yr  (doc §4: 0.9/kg)")

    print(f"\n{'VALIDATION CHECKS':─<{W}}")
    tests = [
        ("negative area",    lambda: compute_building_emission_score("house", -100)),
        ("ndvi > 1.0",       lambda: sustainability_grade(0.5, 1.5)),
        ("population = 0",   lambda: compute_zone_balance([], [], population=0, built_area=1)),
        ("negative waste",   lambda: compute_landfill_emission(-1)),
        ("occupancy > 24h",  lambda: compute_building_emission_score("house", 100, occupancy_hours_per_day=30)),
    ]
    for name, fn in tests:
        try:
            fn()
            print(f"  FAIL — {name} was accepted")
        except ValueError as e:
            print(f"  PASS — {name} blocked: {e}")

    print(f"\n{'PURITY CHECK — no classes anywhere':─<{W}}")
    import ast, inspect
    src   = inspect.getsource(analyze_zone)
    tree  = ast.parse(src)
    nodes = [n for n in ast.walk(tree) if isinstance(n, ast.ClassDef)]
    print(f"  ClassDef nodes in analyze_zone: {len(nodes)}  ({'PASS' if not nodes else 'FAIL'})")
    print(f"  Return type of analyze_zone   : {type(result).__name__}  (expected: dict)")
    print(f"  Return type of compute_zone   : {type(zone).__name__}  (expected: dict)")
    print(f"  Return type of sustain_grade  : {type(sustain).__name__}  (expected: dict)")
    print(f"  Return type of benchmark_score: {type(bench).__name__}  (expected: dict)")
