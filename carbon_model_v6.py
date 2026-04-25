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

from __future__ import annotations
from typing import TypedDict


# =============================================================================
# 1. GLOBAL DOC CONSTANTS  (geo_emissions.md)
# =============================================================================

CH4_GWP  = 28    # doc §7: CH₄ ≈ 28 × CO₂
N2O_GWP  = 265   # doc §7: N₂O ≈ 265 × CO₂

COAL_EF  = 820   # doc §2: coal → 820 g CO₂/kWh  ← ceiling for all grid ratios
GAS_EF   = 490   # doc §2: gas  → 490 g CO₂/kWh

TREE_ABSORPTION_KG_CO2_YR  = 22.5   # doc §8: 1 tree → 20–25 kg CO₂/yr, midpoint
CATTLE_CH4_KG_YR           = 95.0   # doc §3: 70–120 kg CH₄/cow/yr, midpoint
CATTLE_CO2E_KG_YR          = CATTLE_CH4_KG_YR * CH4_GWP        # = 2,660
LANDFILL_CH4_KG_PER_TON    = 75.0   # doc §5: 50–100 kg CH₄/t, midpoint
LANDFILL_CO2E_KG_PER_TON   = LANDFILL_CH4_KG_PER_TON * CH4_GWP # = 2,100
CEMENT_CO2_KG_PER_KG       = 0.9    # doc §4: 0.9 t CO₂ / t cement
GASOLINE_CO2_KG_PER_LITRE  = 2.3    # doc §2: 1 L gasoline → 2.3 kg CO₂

GLOBAL_GHG_GT_CO2E_YR   = 52.5   # doc §1: 50–55 Gt, midpoint
GLOBAL_ABSORPTION_GT_YR = 22.5   # doc §8: 20–25 Gt, midpoint
GLOBAL_DEFICIT_GT_YR    = GLOBAL_GHG_GT_CO2E_YR - GLOBAL_ABSORPTION_GT_YR  # 30 Gt
GLOBAL_BALANCE_RATIO    = GLOBAL_ABSORPTION_GT_YR / GLOBAL_GHG_GT_CO2E_YR  # ≈ 0.429

# Scoring targets
URBAN_GOOD_PER_CAPITA        = 2_500   # kg CO₂/person/yr — ambitious urban target
URBAN_BAD_PER_CAPITA         = 8_000   # kg CO₂/person/yr — high-emission city
SUSTAINABLE_BUILDING_TARGET  = 20.0    # kg CO₂/m²/yr — CRREM 2030 pathway target
# FIX-4: replaced magic _GLOBAL_BUILDING_INTENSITY_CALC (51.45) with named constant
# Source: IEA global buildings report 2023 — global average ~55 kg CO₂/m²/yr
GLOBAL_URBAN_INTENSITY_KG_M2_YR = 55.0
BUILDING_LIFESPAN_YEARS = 50


# =============================================================================
# 2. ELECTRICITY GRID FACTORS (g CO₂ / kWh)
#    Source: IEA Emissions Factors 2025, Ember 2023
# =============================================================================

COUNTRY_GRID_FACTORS: dict[str, float] = {
    "india":     700,   # 713 g/kWh  Ember 2023
    "china":     550,   # 560 g/kWh  Ember 2023
    "poland":    700,   # coal-heavy
    "egypt":     450,   # gas + renewables  IEA 2023
    "usa":       380,   # 366 g/kWh  US EIA 2023
    "germany":   380,   # transitioning  Ember 2023
    "australia": 490,
    "uk":        230,   # gas + wind
    "norway":     30,   # near-zero — hydro  Ember 2023
    "france":     60,   # nuclear
    "brazil":     90,   # hydro
    "default":   500,   # 481 g/kWh  Ember global avg 2023
}

# =============================================================================
# 3. THERMAL (HEATING) EMISSION FACTORS (kg CO₂ / kWh thermal)
#    FIX-1 from v5.4: was a single 0.20 constant for all countries.
#
#    These reflect the dominant heating fuel in each country:
#      Gas boiler:        ~0.20 kg CO₂/kWh  (natural gas, standard)
#      Oil boiler:        ~0.27 kg CO₂/kWh
#      Coal heating:      ~0.34 kg CO₂/kWh
#      District heating:  ~0.07–0.15 kg CO₂/kWh (depends on source)
#      Heat pump (elec):  grid-dependent (handled via elec pathway, not here)
#    Sources: IPCC AR6 WG3 Ch.9; IEA World Energy Outlook fuel EFs
# =============================================================================

COUNTRY_THERMAL_EF: dict[str, float] = {
    # Gas-dominant heating
    "egypt":     0.20,   # gas boiler standard
    "usa":       0.19,   # mixed gas/oil — EIA RECS 2020
    "uk":        0.20,   # gas-dominant — BEIS 2023
    "australia": 0.20,   # gas + some electric
    "brazil":    0.10,   # low — much is biomass/hydro electric
    "france":    0.07,   # district heating mostly nuclear electric
    "norway":    0.03,   # district heating from hydro — near-zero
    # Coal-heavy heating
    "poland":    0.34,   # coal heating dominant — Eurostat 2022
    "china":     0.30,   # coal district heating in north
    "india":     0.30,   # coal + biomass mix
    # Mixed
    "germany":   0.22,   # gas + some district heating — UBA 2023
    "default":   0.20,   # global gas boiler default
}


# =============================================================================
# 4. BUILDING EUI (kWh / m² / yr)
#    Source: ScienceDirect EUI review 2023 — 3,060 buildings
#    Hospital/Office median: 164–174 kWh/m²/yr
#    Retail median: 303 kWh/m²/yr (highest category)
#    Residential median: 87 kWh/m²/yr
#    Educational median: 117 kWh/m²/yr
# =============================================================================

BUILDING_EUI_KWH_M2_YR: dict[str, float] = {
    "house":       120.0,
    "detached":    120.0,
    "apartments":   85.0,
    "residential": 105.0,
    "commercial":  240.0,
    "office":      170.0,
    "retail":      303.0,
    "supermarket": 380.0,
    "school":      117.0,
    "university":  200.0,
    "hospital":    164.0,
    "government":  110.0,
    "industrial":  350.0,
    "factory":     320.0,
    "warehouse":    45.0,
    "fuel":        200.0,
    "parking":      25.0,
    "default":     110.0,
}


# =============================================================================
# 5. BASE ELECTRICITY SHARE BY BUILDING TYPE
#    Source: EIA CBECS 2018 [^49^], EIA RECS/CBECS cooling [^47^][^48^]
#    Commercial nationally: 60% electricity, 34% natural gas
#    Hot climates (South US): 69% electricity, 26% gas
# =============================================================================

BASE_ELEC_SHARE: dict[str, float] = {
    "house":       0.40,   # EIA CBECS 2018 — raised from 0.35 in v5.4
    "detached":    0.40,
    "apartments":  0.45,
    "residential": 0.42,
    "commercial":  0.55,
    "office":      0.60,
    "retail":      0.55,
    "supermarket": 0.75,   # high refrigeration load
    "school":      0.50,
    "university":  0.60,
    "hospital":    0.70,   # medical equipment + HVAC
    "government":  0.50,
    "industrial":  0.45,
    "factory":     0.45,
    "warehouse":   0.30,   # low lighting + minimal HVAC
    "fuel":        0.80,
    "parking":     0.90,   # almost entirely lighting
    "default":     0.50,
}


# =============================================================================
# 6. EMBODIED CARBON (kg CO₂ / m² / yr  — annualised over 50-yr lifespan)
#    Sources: SBTi/CRREM 2024, OneClickLCA 2021, Rock et al. 2021,
#             Denmark BR 2023, JRC European Commission 2020,
#             ScienceDirect 2025 (US commercial embodied carbon)
# =============================================================================

BUILDING_EMBODIED_KG_M2_YR: dict[str, float] = {
    "house":        8.1,
    "detached":     8.1,
    "apartments":   7.0,
    "residential":  7.6,
    "commercial":  10.2,
    "office":      11.4,
    "retail":      10.0,
    "supermarket": 11.0,
    "school":       7.6,
    "university":   9.0,
    "hospital":    16.0,   # complex MEP systems, specialist materials
    "government":   8.0,
    "industrial":  10.0,
    "factory":      9.6,
    "warehouse":    6.0,
    "fuel":         7.0,
    "parking":      5.0,
    "default":      8.0,
}


# =============================================================================
# 7. CLIMATE ZONE MULTIPLIERS
#    Source: EIA CBECS South region — ~15% higher electricity vs national avg
#    Hot:  1.15 (corrected in v5.4 from 1.25)
#    Cold: 1.20 — heating penalty
# =============================================================================

HOT_CLIMATES  = {"egypt", "india", "brazil", "australia"}
COLD_CLIMATES = {"usa", "germany", "uk", "norway", "france", "poland", "china"}

CLIMATE_MULT_HOT  = 1.15
CLIMATE_MULT_COLD = 1.20


# =============================================================================
# 8. INDUSTRIAL PROCESS MULTIPLIERS
#    Anchored to doc §4: cement = 0.9 t CO₂/t product
#    factory=1.30 → 30% process overhead (steel/chemicals)
#    industrial=1.40 → 40% overhead (cement + heavy chemical)
# =============================================================================

INDUSTRIAL_PROCESS_MULTIPLIER: dict[str, float] = {
    "factory":    1.30,
    "industrial": 1.40,
    "warehouse":  1.00,
    "default":    1.00,
}


# =============================================================================
# 9. ROAD TRANSPORT  (kg CO₂ / m² road area / yr)
#    Back-calculated from EPA 2024 vehicle factors:
#      Passenger car: 0.306 kg CO₂/vehicle-mile (≈ 0.190 kg/veh-km)
#    Assumed traffic densities per road class applied to
#    doc §2 anchor: 1 L gasoline = 2.3 kg CO₂ (GASOLINE_CO2_KG_PER_LITRE)
#    STATUS: order-of-magnitude proxy — no direct published per-m² source.
# =============================================================================

ROAD_INTENSITY_KG_M2_YR: dict[str, float] = {
    "motorway":    35.0,
    "primary":     25.0,
    "secondary":   15.0,
    "tertiary":    10.0,
    "residential":  8.0,
    "service":      5.0,
    "default":      5.0,
}


# =============================================================================
# 10. NON-ROAD TRANSPORT  (kg CO₂ / yr per unit)
#     FIX-2 from v5.4: airport was 150,000/runway which overwhelmed small zones.
#
#     These factors now represent ON-SITE emissions only (fuel burn at the
#     facility boundary — ground vehicles, taxiing, APU, heating).
#     Network emissions (flights, rail journeys) are NOT attributed to
#     the OSM polygon — they belong to the network-level analysis.
#
#     Rail: VERIFIED — UIC/ERA 2024: 50 tCO₂/km/yr standard corridor [^62^]
#           Represents track infrastructure + maintenance, not train journeys.
#     Airport: REVISED DOWN — on-site only (ground support, terminal, heating)
#              ICAO CORSIA handles per-flight; here we proxy terminal only.
#     Port: REVISED DOWN — on-site fuel (cranes, tugs, terminal equipment)
#     Helipad: ~1% of small airport terminal load
# =============================================================================

NON_ROAD_TRANSPORT_EF: dict[str, float] = {
    "rail":      50_000.0,   # kg CO₂/km track/yr — UIC/ERA 2024 VERIFIED
    "airport":   25_000.0,   # kg CO₂/runway/yr — on-site only (REVISED from 150,000)
    "port":      40_000.0,   # kg CO₂/berth/yr — on-site only (REVISED from 250,000)
    "helipad":    1_500.0,   # kg CO₂/pad/yr — estimated
    "default":        0.0,
}

NON_ROAD_NOTE = """
NON-ROAD TRANSPORT NOTE (v6.0):
- Rail: VERIFIED (UIC/ERA 2024) — infrastructure lifecycle, not train journeys
- Airport/Port: ON-SITE ONLY — terminal + ground equipment fuel burn
  Network emissions (flights, vessels) NOT included — use ICAO/IMO tools for those
- All values: ESTIMATED PROXIES for comparative scoring only
"""


# =============================================================================
# 11. GREEN AREA ABSORPTION  (kg CO₂ / m² / yr)
#     Source: IPCC AFOLU; doc §8: 1 ha forest = 10–20 t CO₂/yr
#     1 ha = 10,000 m²  →  forest = 1.0–2.0 kg/m²/yr, midpoint 1.50
# =============================================================================

ABSORPTION_CAPACITY_KG_M2_YR: dict[str, float] = {
    "forest":   1.50,   # doc §8 midpoint: 15 t/ha ÷ 10,000 m²
    "wood":     1.30,
    "wetland":  1.20,
    "park":     0.80,
    "garden":   0.50,
    "scrub":    0.40,
    "grass":    0.30,
    "farmland": 0.20,
    "default":  0.00,
}


# =============================================================================
# 12. POPULATION DENSITY MULTIPLIER
# =============================================================================

def population_density_multiplier(pop_density_per_km2: float) -> float:
    """
    Urban density scaling: [1.0, 2.0].
    At 0/km²       → 1.0 (rural, no scaling)
    At 20,000/km²  → 2.0 (dense city core, capped)
    """
    return min(1.0 + (max(pop_density_per_km2, 0.0) / 20_000.0), 2.0)


# =============================================================================
# 13. INPUT VALIDATION  (FIX-3)
# =============================================================================

def _validate_area(area_m2: float, name: str = "area_m2") -> None:
    """Raise ValueError for physically impossible inputs."""
    if area_m2 < 0:
        raise ValueError(f"{name} cannot be negative (got {area_m2})")


def _validate_ratio(value: float, lo: float, hi: float, name: str) -> None:
    if not (lo <= value <= hi):
        raise ValueError(f"{name} must be in [{lo}, {hi}] (got {value})")


# =============================================================================
# 14. BUILDING EMISSION CALCULATION
# =============================================================================

class BuildingResult(TypedDict):
    building_type:      str
    area_m2:            float
    e_thermal_kg_yr:    float   # gas/oil/coal heating
    e_elec_kg_yr:       float   # electricity (grid-scaled)
    e_process_kg_yr:    float   # industrial process overhead
    e_embodied_kg_yr:   float   # annualised embodied carbon
    e_total_kg_yr:      float
    e_low_kg_yr:        float   # –20% uncertainty
    e_high_kg_yr:       float   # +20% uncertainty
    intensity_kg_m2_yr: float
    energy_kwh_m2_yr:   float
    elec_share:         float
    thermal_ef_used:    float   # FIX-1: now shows which thermal EF was applied
    climate_mult:       float


def compute_building_emission_score(
    building_type:           str,
    area_m2:                 float,
    country:                 str   = "default",
    occupancy_hours_per_day: float = 10.0,
    pop_density_per_km2:     float = 5_000,
) -> BuildingResult:
    """
    Annual CO₂ emissions for a single OSM building polygon.

    Formula:
      E = (E_thermal + E_elec) × density_mult × process_mult + E_embodied
      E_thermal = EUI × (1 - elec_share) × thermal_ef × area
      E_elec    = EUI × elec_share × climate_mult × grid_ef × area
    """
    # FIX-3: validate inputs
    _validate_area(area_m2)
    _validate_ratio(occupancy_hours_per_day, 0, 24, "occupancy_hours_per_day")

    eui        = BUILDING_EUI_KWH_M2_YR.get(building_type, BUILDING_EUI_KWH_M2_YR["default"])
    base_elec  = BASE_ELEC_SHARE.get(building_type, BASE_ELEC_SHARE["default"])

    # Occupancy shifts elec share slightly (more hours = more lighting/equipment)
    occupancy_frac  = occupancy_hours_per_day / 24.0
    occupancy_delta = (occupancy_frac - 0.5) * 0.20
    elec_share      = min(max(base_elec + occupancy_delta, 0.10), 0.90)
    thermal_share   = 1.0 - elec_share

    # FIX-1: per-country thermal emission factor
    thermal_ef = COUNTRY_THERMAL_EF.get(country.lower(), COUNTRY_THERMAL_EF["default"])

    # Climate multiplier on electricity (cooling/heating load)
    climate_mult = 1.0
    c = country.lower()
    if c in HOT_CLIMATES:
        climate_mult = CLIMATE_MULT_HOT
    elif c in COLD_CLIMATES:
        climate_mult = CLIMATE_MULT_COLD

    grid_factor      = COUNTRY_GRID_FACTORS.get(c, COUNTRY_GRID_FACTORS["default"])
    grid_ef_kg_co2   = grid_factor / 1_000.0   # g/kWh → kg/kWh

    # Per-m² intensities before area scaling
    thermal_intensity = eui * thermal_share * thermal_ef
    elec_intensity    = eui * elec_share * climate_mult * grid_ef_kg_co2

    density_mult  = population_density_multiplier(pop_density_per_km2)
    process_mult  = INDUSTRIAL_PROCESS_MULTIPLIER.get(
        building_type, INDUSTRIAL_PROCESS_MULTIPLIER["default"]
    )
    embodied_intensity = BUILDING_EMBODIED_KG_M2_YR.get(
        building_type, BUILDING_EMBODIED_KG_M2_YR["default"]
    )

    e_thermal  = area_m2 * thermal_intensity * density_mult
    e_elec     = area_m2 * elec_intensity    * density_mult
    e_process  = area_m2 * (thermal_intensity + elec_intensity) * density_mult * (process_mult - 1.0)
    e_embodied = area_m2 * embodied_intensity   # embodied not density-scaled
    e_total    = e_thermal + e_elec + e_process + e_embodied

    return BuildingResult(
        building_type      = building_type,
        area_m2            = round(area_m2, 1),
        e_thermal_kg_yr    = round(e_thermal, 1),
        e_elec_kg_yr       = round(e_elec, 1),
        e_process_kg_yr    = round(e_process, 1),
        e_embodied_kg_yr   = round(e_embodied, 1),
        e_total_kg_yr      = round(e_total, 1),
        e_low_kg_yr        = round(e_total * 0.80, 1),
        e_high_kg_yr       = round(e_total * 1.20, 1),
        intensity_kg_m2_yr = round(
            (thermal_intensity + elec_intensity) * process_mult * density_mult
            + embodied_intensity, 3
        ),
        energy_kwh_m2_yr   = round(eui, 1),
        elec_share         = round(elec_share, 3),
        thermal_ef_used    = thermal_ef,   # FIX-1: visible in output
        climate_mult       = round(climate_mult, 2),
    )


# =============================================================================
# 15. ROAD TRANSPORT
# =============================================================================

def compute_transport_emission(
    road_type:           str,
    area_m2:             float,
    pop_density_per_km2: float = 5_000,
) -> float:
    """kg CO₂/yr for a road polygon. Proxy from EPA 2024 vehicle EFs."""
    _validate_area(area_m2)
    intensity = ROAD_INTENSITY_KG_M2_YR.get(road_type, ROAD_INTENSITY_KG_M2_YR["default"])
    intensity *= population_density_multiplier(pop_density_per_km2)
    return round(area_m2 * intensity, 1)


# =============================================================================
# 16. DOC-DERIVED STANDALONE FUNCTIONS  (ADD-1 through ADD-4)
# =============================================================================

def compute_tree_absorption(tree_count: int) -> float:
    """doc §8: 1 tree → 20–25 kg CO₂/yr, midpoint 22.5."""
    if tree_count < 0:
        raise ValueError(f"tree_count cannot be negative (got {tree_count})")
    return round(tree_count * TREE_ABSORPTION_KG_CO2_YR, 1)


def compute_livestock_emission(cattle_count: int) -> float:
    """doc §3 + §7: each cow → 95 kg CH₄/yr × GWP28 = 2,660 kg CO₂e."""
    if cattle_count < 0:
        raise ValueError(f"cattle_count cannot be negative")
    return round(cattle_count * CATTLE_CO2E_KG_YR, 1)


def compute_landfill_emission(waste_tonnes: float) -> float:
    """doc §5 + §7: 1 t waste → 75 kg CH₄ × GWP28 = 2,100 kg CO₂e."""
    if waste_tonnes < 0:
        raise ValueError(f"waste_tonnes cannot be negative")
    return round(waste_tonnes * LANDFILL_CO2E_KG_PER_TON, 1)


def compute_cement_emission(cement_tonnes: float) -> float:
    """doc §4: 0.9 t CO₂ / t cement."""
    if cement_tonnes < 0:
        raise ValueError(f"cement_tonnes cannot be negative")
    return round(cement_tonnes * 1_000 * CEMENT_CO2_KG_PER_KG, 1)


# =============================================================================
# 17. ZONE CARBON BALANCE
# =============================================================================

class ZoneBalance(TypedDict):
    building_emission_kg_yr:   float
    embodied_emission_kg_yr:   float
    transport_emission_kg_yr:  float
    non_road_emission_kg_yr:   float
    livestock_emission_kg_yr:  float
    landfill_emission_kg_yr:   float
    total_emission_kg_yr:      float
    tree_absorption_kg_yr:     float
    area_absorption_kg_yr:     float
    total_absorption_kg_yr:    float
    balance_kg_yr:             float
    balance_ratio:             float
    global_balance_ratio:      float   # context: doc §1 + §8 → 0.429
    emission_low_kg_yr:        float
    emission_high_kg_yr:       float
    per_capita_kg_yr:          float
    intensity_kg_m2_yr:        float
    building_details:          list[BuildingResult]


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
) -> ZoneBalance:
    """
    Full carbon balance for an OSM-derived zone.
    doc §9: E = Σ(Activity × EF),  S = Area × Absorption_Rate
    """
    # FIX-8: validate denominators
    if population <= 0:
        raise ValueError("population must be > 0 for per-capita calculation")
    if built_area <= 0:
        raise ValueError("built_area must be > 0 for intensity calculation")

    roads     = roads     or []
    non_roads = non_roads or []

    # ── Emissions ─────────────────────────────────────────────────────────────
    building_details = [
        compute_building_emission_score(
            building_type           = b["type"],
            area_m2                 = b["area_m2"],
            country                 = country,
            occupancy_hours_per_day = b.get("occupancy_hours", 10.0),
            pop_density_per_km2     = pop_density_per_km2,
        )
        for b in buildings
    ]

    e_buildings = sum(r["e_total_kg_yr"]    for r in building_details)
    e_embodied  = sum(r["e_embodied_kg_yr"] for r in building_details)
    e_transport = sum(
        compute_transport_emission(r["type"], r["area_m2"], pop_density_per_km2)
        for r in roads
    )
    e_non_road  = sum(
        NON_ROAD_TRANSPORT_EF.get(nr["type"], NON_ROAD_TRANSPORT_EF["default"])
        * nr.get("count", 1)
        for nr in non_roads
    )
    e_livestock = compute_livestock_emission(cattle_count)
    e_landfill  = compute_landfill_emission(waste_tonnes)

    e_total = e_buildings + e_transport + e_non_road + e_livestock + e_landfill

    # ── Absorption ────────────────────────────────────────────────────────────
    s_area  = sum(
        ABSORPTION_CAPACITY_KG_M2_YR.get(g["type"], ABSORPTION_CAPACITY_KG_M2_YR["default"])
        * g["area_m2"]
        for g in green_areas
    )
    s_trees = compute_tree_absorption(tree_count)
    s_total = s_area + s_trees

    balance       = s_total - e_total
    balance_ratio = s_total / max(e_total, 1.0)

    return ZoneBalance(
        building_emission_kg_yr  = round(e_buildings, 1),
        embodied_emission_kg_yr  = round(e_embodied, 1),
        transport_emission_kg_yr = round(e_transport, 1),
        non_road_emission_kg_yr  = round(e_non_road, 1),
        livestock_emission_kg_yr = round(e_livestock, 1),
        landfill_emission_kg_yr  = round(e_landfill, 1),
        total_emission_kg_yr     = round(e_total, 1),
        tree_absorption_kg_yr    = round(s_trees, 1),
        area_absorption_kg_yr    = round(s_area, 1),
        total_absorption_kg_yr   = round(s_total, 1),
        balance_kg_yr            = round(balance, 1),
        balance_ratio            = round(balance_ratio, 4),
        global_balance_ratio     = round(GLOBAL_BALANCE_RATIO, 4),
        emission_low_kg_yr       = round(e_total * 0.80, 1),
        emission_high_kg_yr      = round(e_total * 1.20, 1),
        per_capita_kg_yr         = round(e_total / population, 1),
        intensity_kg_m2_yr       = round(e_total / built_area, 3),
        building_details         = building_details,
    )


# =============================================================================
# 18. NORMALIZE
# =============================================================================

def normalize(value: float, good: float, bad: float, higher_is_better: bool = False) -> float:
    """Clamp-and-scale value to [0.0, 1.0]."""
    if higher_is_better:
        if value >= good: return 1.0
        if value <= bad:  return 0.0
        return (value - bad) / (good - bad)
    else:
        if value <= good: return 1.0
        if value >= bad:  return 0.0
        return 1.0 - (value - good) / (bad - good)


# =============================================================================
# 19. SUSTAINABILITY GRADE  (FIX-6: now includes breakdown dict)
#     70% carbon balance (doc §5: primary), 30% NDVI (secondary)
#     Ceiling ratio = 1.2 → ratio ≥ 1.2 earns full 70 carbon pts
# =============================================================================

class GradeResult(TypedDict):
    score:          float
    grade:          str
    carbon_score:   float
    ndvi_score:     float
    label:          str
    recommendation: str
    breakdown:      dict   # FIX-6: explains which input drives the grade


_GRADE_LABELS: dict[str, tuple[str, str]] = {
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


def sustainability_grade(balance_ratio: float, ndvi: float) -> GradeResult:
    """
    A–F grade.  doc §5: Health = f(CO₂_balance, green_coverage)
    Carbon: 70 pts (primary).  NDVI: 30 pts (secondary).
    """
    _validate_ratio(ndvi, 0.0, 1.0, "ndvi")

    carbon_component = min(balance_ratio, 1.2) / 1.2
    ndvi_component   = min(max(ndvi, 0.0), 1.0)

    carbon_score = carbon_component * 70.0
    ndvi_score   = ndvi_component   * 30.0
    total_score  = carbon_score + ndvi_score

    if   total_score >= 85: grade = "A"
    elif total_score >= 70: grade = "B"
    elif total_score >= 55: grade = "C"
    elif total_score >= 40: grade = "D"
    else:                   grade = "F"

    label, recommendation = _GRADE_LABELS[grade]

    # FIX-6: breakdown explains the grade to the frontend
    limiting = "carbon balance" if carbon_score < ndvi_score * (70/30) else "vegetation (NDVI)"
    breakdown = {
        "carbon_score":         round(carbon_score, 2),
        "carbon_max":           70,
        "ndvi_score":           round(ndvi_score, 2),
        "ndvi_max":             30,
        "limiting_factor":      limiting,
        "balance_ratio_used":   round(balance_ratio, 4),
        "ndvi_used":            round(ndvi, 3),
        "global_ratio_context": round(GLOBAL_BALANCE_RATIO, 4),
    }

    return GradeResult(
        score          = round(total_score, 2),
        grade          = grade,
        carbon_score   = round(carbon_score, 2),
        ndvi_score     = round(ndvi_score, 2),
        label          = label,
        recommendation = recommendation,
        breakdown      = breakdown,
    )


# =============================================================================
# 20. BENCHMARK SCORE  (FIX-5: weights now documented)
#
#     Three independent metrics normalised to [0, 100] then weighted:
#       45% per-capita emissions  — most direct human impact signal
#       25% building intensity    — measures built environment quality
#       30% ecology balance       — absorption vs emission ratio
#
#     Weight rationale:
#       Per-capita (45%) is the primary UNFCCC / Paris Agreement metric.
#       Ecology (30%) reflects the doc's emphasis on carbon balance.
#       Building intensity (25%) is important but partially captured by per-capita.
# =============================================================================

class BenchmarkResult(TypedDict):
    final_score:    float
    carbon_score:   float
    building_score: float
    ecology_score:  float
    grade:          str

# FIX-5: named weights instead of inline 0.45/0.25/0.30
BENCHMARK_WEIGHT_CARBON   = 0.45   # per-capita emissions — UNFCCC primary metric
BENCHMARK_WEIGHT_BUILDING = 0.25   # building intensity — built environment quality
BENCHMARK_WEIGHT_ECOLOGY  = 0.30   # balance ratio — doc §9 absorption vs emission


def benchmark_score(zone: ZoneBalance) -> BenchmarkResult:
    """
    Target-based benchmarking against published urban decarbonisation targets.
    Three signals weighted 45/25/30 (see constants above for rationale).
    """
    carbon_score = normalize(
        zone["per_capita_kg_yr"],
        URBAN_GOOD_PER_CAPITA,        # 2,500 kg/person — ambitious urban target
        URBAN_BAD_PER_CAPITA,         # 8,000 kg/person — high-emission city
        higher_is_better=False,
    ) * 100

    building_score = normalize(
        zone["intensity_kg_m2_yr"],
        SUSTAINABLE_BUILDING_TARGET,       # 20 kg/m² — CRREM 2030 pathway
        GLOBAL_URBAN_INTENSITY_KG_M2_YR,   # 55 kg/m² — IEA global avg (FIX-4)
        higher_is_better=False,
    ) * 100

    ecology_score = normalize(
        zone["balance_ratio"],
        1.2,   # good: absorption 20% above emissions
        0.3,   # bad:  absorption only 30% of emissions
        higher_is_better=True,
    ) * 100

    final_score = (
        carbon_score   * BENCHMARK_WEIGHT_CARBON   +
        building_score * BENCHMARK_WEIGHT_BUILDING +
        ecology_score  * BENCHMARK_WEIGHT_ECOLOGY
    )

    if   final_score >= 85: bgrade = "A"
    elif final_score >= 70: bgrade = "B"
    elif final_score >= 55: bgrade = "C"
    elif final_score >= 40: bgrade = "D"
    else:                   bgrade = "F"

    return BenchmarkResult(
        final_score    = round(final_score, 2),
        carbon_score   = round(carbon_score, 2),
        building_score = round(building_score, 2),
        ecology_score  = round(ecology_score, 2),
        grade          = bgrade,
    )


# =============================================================================
# 21. UNIFIED API
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
    """Single call returning zone metrics + both scoring systems."""
    zone = compute_zone_balance(
        buildings           = buildings,
        green_areas         = green_areas,
        roads               = roads,
        non_roads           = non_roads,
        cattle_count        = cattle_count,
        waste_tonnes        = waste_tonnes,
        tree_count          = tree_count,
        country             = country,
        pop_density_per_km2 = pop_density_per_km2,
        population          = population,
        built_area          = built_area,
    )
    sustain = sustainability_grade(zone["balance_ratio"], ndvi)
    bench   = benchmark_score(zone)
    return {
        "zone_metrics":   zone,
        "sustainability": sustain,
        "benchmark":      bench,
    }


# =============================================================================
# 22. SELF-TEST  (FIX-7: realistic urban zone, no airport/port)
# =============================================================================

if __name__ == "__main__":

    # Realistic mid-size urban zone in Egypt (~50,000 m² total footprint)
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
        {"type": "primary",    "area_m2": 1_200},
        {"type": "secondary",  "area_m2":   900},
        {"type": "residential","area_m2":   600},
    ]
    non_roads = [
        {"type": "rail", "count": 1},   # 1 km of track through the zone
    ]

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
    print("ECOBALANCE v6.0 — SELF TEST (EGYPT, URBAN ZONE)")
    print("=" * W)

    print("\nv6.0 FIXES APPLIED:")
    print("  FIX-1  Per-country thermal EF (Poland coal != Norway hydro)")
    print("  FIX-2  Non-road revised to on-site only (airport/port no longer dominant)")
    print("  FIX-3  Input validation (negative areas now raise ValueError)")
    print("  FIX-4  Benchmark bad-intensity from magic 51.45 → GLOBAL_URBAN_INTENSITY=55")
    print("  FIX-5  Benchmark weights documented (45/25/30 with rationale)")
    print("  FIX-6  Grade breakdown dict added (limiting factor visible)")
    print("  FIX-7  Self-test uses realistic zone (no airport/port domination)")
    print("  FIX-8  population/built_area validated > 0")
    print("  ADD-1–4  Tree/livestock/landfill/cement functions from doc §3,§4,§5,§8")

    print(f"\n{'ZONE METRICS':─<{W}}")
    print(f"  Building emissions   : {zone['building_emission_kg_yr']:>12,.1f} kg CO₂/yr")
    print(f"  ├─ Operational       : {zone['building_emission_kg_yr']-zone['embodied_emission_kg_yr']:>12,.1f} kg CO₂/yr")
    print(f"  └─ Embodied          : {zone['embodied_emission_kg_yr']:>12,.1f} kg CO₂/yr")
    print(f"  Road transport       : {zone['transport_emission_kg_yr']:>12,.1f} kg CO₂/yr")
    print(f"  Non-road transport   : {zone['non_road_emission_kg_yr']:>12,.1f} kg CO₂/yr  (on-site only)")
    print(f"  Landfill             : {zone['landfill_emission_kg_yr']:>12,.1f} kg CO₂e/yr  (doc §5)")
    print(f"  ─────────────────────────────────────────────────────────")
    print(f"  Total emissions      : {zone['total_emission_kg_yr']:>12,.1f} kg CO₂/yr")
    print(f"  Area absorption      : {zone['area_absorption_kg_yr']:>12,.1f} kg CO₂/yr")
    print(f"  Tree absorption      : {zone['tree_absorption_kg_yr']:>12,.1f} kg CO₂/yr  (200 trees, doc §8)")
    print(f"  Total absorption     : {zone['total_absorption_kg_yr']:>12,.1f} kg CO₂/yr")
    print(f"  ─────────────────────────────────────────────────────────")
    print(f"  Net balance          : {zone['balance_kg_yr']:>12,.1f} kg CO₂/yr")
    print(f"  Balance ratio        : {zone['balance_ratio']:>12.4f}  (global ref: {zone['global_balance_ratio']:.4f})")
    print(f"  Per-capita           : {zone['per_capita_kg_yr']:>12,.1f} kg/person/yr")
    print(f"  Intensity            : {zone['intensity_kg_m2_yr']:>12.3f} kg/m²/yr")
    print(f"  Uncertainty range    : {zone['emission_low_kg_yr']:,.0f} – {zone['emission_high_kg_yr']:,.0f} kg/yr")

    print(f"\n{'SUSTAINABILITY GRADE (70% carbon / 30% NDVI)':─<{W}}")
    print(f"  Grade            : {sustain['grade']}")
    print(f"  Score            : {sustain['score']} / 100")
    print(f"  Carbon score     : {sustain['carbon_score']} / 70")
    print(f"  NDVI score       : {sustain['ndvi_score']} / 30")
    print(f"  Limiting factor  : {sustain['breakdown']['limiting_factor']}")
    print(f"  Label            : {sustain['label']}")
    print(f"  Recommendation   : {sustain['recommendation']}")

    print(f"\n{'BENCHMARK SCORE (45% per-capita / 25% intensity / 30% ecology)':─<{W}}")
    print(f"  Grade            : {bench['grade']}")
    print(f"  Final score      : {bench['final_score']} / 100")
    print(f"  Per-capita score : {bench['carbon_score']:.1f} / 45")
    print(f"  Building score   : {bench['building_score']:.1f} / 25")
    print(f"  Ecology score    : {bench['ecology_score']:.1f} / 30")

    print(f"\n{'BUILDING BREAKDOWN':─<{W}}")
    print(f"  {'Type':<14} {'EUI':>6}  {'thermal_ef':>10}  {'thermal':>9}  {'elec':>9}  {'proc':>7}  {'embod':>7}  {'total':>10}")
    print(f"  {'─'*14} {'─'*6}  {'─'*10}  {'─'*9}  {'─'*9}  {'─'*7}  {'─'*7}  {'─'*10}")
    for b in zone["building_details"]:
        print(
            f"  {b['building_type']:<14}"
            f" {b['energy_kwh_m2_yr']:>5.0f}kWh"
            f"  ef={b['thermal_ef_used']:.3f}     "
            f"  {b['e_thermal_kg_yr']:>9,.0f}"
            f"  {b['e_elec_kg_yr']:>9,.0f}"
            f"  {b['e_process_kg_yr']:>7,.0f}"
            f"  {b['e_embodied_kg_yr']:>7,.0f}"
            f"  {b['e_total_kg_yr']:>10,.0f}"
        )

    print(f"\n{'STANDALONE FUNCTION CHECKS (doc constants)':─<{W}}")
    print(f"  compute_tree_absorption(200)       : {compute_tree_absorption(200):,.1f} kg CO₂/yr  (doc §8: 22.5/tree)")
    print(f"  compute_livestock_emission(10)     : {compute_livestock_emission(10):,.1f} kg CO₂e/yr (doc §3: 95×28)")
    print(f"  compute_landfill_emission(2.0)     : {compute_landfill_emission(2.0):,.1f} kg CO₂e/yr (doc §5: 75×28)")
    print(f"  compute_cement_emission(100)       : {compute_cement_emission(100):,.1f} kg CO₂/yr  (doc §4: 0.9/kg)")

    print(f"\n{'VALIDATION CHECK':─<{W}}")
    try:
        compute_building_emission_score("house", -100)
        print("  FAIL: negative area accepted")
    except ValueError as e:
        print(f"  PASS: negative area blocked → {e}") 
    try:
        sustainability_grade(0.5, 1.5)
        print("  FAIL: ndvi > 1.0 accepted")
    except ValueError as e:
        print(f"  PASS: ndvi > 1.0 blocked → {e}")
