# EcoBalance Carbon Model v7.0 — Full Technical Documentation & References

> **Disclaimer:** NOT FOR AUDITED CARBON REPORTING  
> Intended for comparative, proxy-based sustainability analysis only.

---

## Overview

EcoBalance is a **geospatial carbon estimation and sustainability scoring engine** designed for:

* Comparative sustainability analysis of urban zones
* Estimating annual carbon emissions / absorption from geospatial land-use data
* Benchmarking urban sustainability performance
* Supporting planning / simulation / academic sustainability projects

It transforms spatial/land-use inputs into:

* Carbon emissions estimates
* Carbon absorption estimates
* Net carbon balance
* Sustainability grades
* Benchmark comparisons

> **Important:**
> This model is for **comparative / planning use only** and **NOT for audited carbon reporting**.

---

## Features

* **Building Emission Modeling**
  * Operational thermal emissions
  * Electricity emissions
  * Industrial process emissions
  * Embodied carbon

* **Transport Modeling**
  * Road transport proxy emissions
  * Rail / airport / port / helipad emissions

* **Additional Emission Sources**
  * Livestock methane
  * Landfill methane
  * Cement production emissions

* **Carbon Absorption Modeling**
  * Green land absorption
  * Tree sequestration

* **Scoring System**
  * Sustainability A–F grade
  * Benchmark performance score
  * Recommendations and breakdowns

---

## Scientific Methodology

The engine implements the generalized emissions framework:

$$
E_{total} = \sum(Activity_i \times EmissionFactor_i)
$$

Where:

* **Activity** = measurable proxy (energy use, floor area, road area, waste, etc.)
* **Emission Factor** = scientifically derived carbon coefficient

Carbon balance:

$$
Balance = Absorption - Emissions
$$

$$
BalanceRatio = \frac{Absorption}{Emissions}
$$

---

## Architecture

```text
INPUT DATA
   ↓
Validation Layer
   ↓
Emission Calculations
   ↓
Absorption Calculations
   ↓
Zone Balance Engine
   ↓
Scoring Engine
   ↓
Benchmark Engine
   ↓
Output Results
```

---

## Input Schema

### Buildings

```python
[
    {
        "type": "apartments",
        "area_m2": 3000,
        "occupancy_hours": 18
    }
]
```

| Field             | Type    | Description                |
| ----------------- | ------- | -------------------------- |
| `type`            | `str`   | Building classification    |
| `area_m2`         | `float` | Building floor area        |
| `occupancy_hours` | `float` | Average occupied hours/day |

### Green Areas

```python
[
    {
        "type": "park",
        "area_m2": 5000
    }
]
```

### Roads

```python
[
    {
        "type": "primary",
        "area_m2": 1200
    }
]
```

### Non-Road Infrastructure

```python
[
    {
        "type": "rail",
        "count": 1
    }
]
```

---

## Core Data Sources / Numeric References

### 1. Global Climate Constants

| Constant                     | Value           | Source                      |
| ---------------------------- | --------------- | --------------------------- |
| CH₄ Global Warming Potential | 28              | IPCC AR6 / geo_emissions §7 |
| N₂O Global Warming Potential | 265             | IPCC AR6 / geo_emissions §7 |
| Global GHG Emissions         | 50–55 GtCO₂e/yr | geo_emissions §1            |
| Global Natural Absorption    | 20–25 GtCO₂/yr  | geo_emissions §8            |

### 2. Electricity Grid Emission Factors

Units: **g CO₂ / kWh**

| Country        | Factor | Source                |
| -------------- | ------ | --------------------- |
| India          | 700    | Ember 2023 / IEA 2025 |
| China          | 550    | Ember 2023            |
| Egypt          | 450    | IEA 2023              |
| USA            | 380    | US EIA 2023           |
| Germany        | 380    | Ember 2023            |
| UK             | 230    | Ember 2023            |
| Norway         | 30     | Ember 2023            |
| France         | 60     | Ember 2023            |
| Brazil         | 90     | Ember 2023            |
| Global Default | 500    | Ember Global Avg 2023 |

### 3. Thermal / Heating Emission Factors

Units: **kg CO₂ / kWh Thermal**

| Country | Factor | Source                     |
| ------- | ------ | -------------------------- |
| Egypt   | 0.20   | IPCC AR6 / Gas Boiler Avg  |
| USA     | 0.19   | EIA RECS 2020              |
| UK      | 0.20   | BEIS 2023                  |
| Poland  | 0.34   | Eurostat 2022              |
| China   | 0.30   | Coal District Heating Avg  |
| Norway  | 0.03   | Hydro District Heating     |
| France  | 0.07   | Nuclear / District Heating |

### 4. Building Energy Use Intensities (EUI)

Units: **kWh / m² / year**

Source: **ScienceDirect Building EUI Meta-Review 2023 (~3,060 buildings)**

| Building Type | EUI |
| ------------- | --- |
| House         | 120 |
| Apartments    | 85  |
| Office        | 170 |
| Commercial    | 240 |
| Retail        | 303 |
| Supermarket   | 380 |
| School        | 117 |
| Hospital      | 164 |
| Industrial    | 350 |
| Warehouse     | 45  |

### 5. Embodied Carbon Intensities

Units: **kg CO₂ / m² / year**  
(Annualized over 50-year lifespan)

Sources: SBTi 2024, CRREM 2024, OneClickLCA, Denmark BR 2023

| Building Type | Embodied Carbon |
| ------------- | --------------- |
| House         | 8.1             |
| Apartments    | 7.0             |
| Office        | 11.4            |
| Hospital      | 16.0            |
| Industrial    | 10.0            |

### 6. Transport Proxies

#### Road Emissions Proxy

Units: **kg CO₂ / m² road / year**

Derived from: EPA 2024 vehicle-mile emissions, geo_emissions §2 gasoline anchor (2.3 kg/L)

| Road Type   | Intensity |
| ----------- | --------- |
| Motorway    | 35        |
| Primary     | 25        |
| Secondary   | 15        |
| Residential | 8         |

#### Non-Road Transport Facilities

Units: **kg CO₂ / year per unit**

| Facility          | Emission | Source               |
| ----------------- | -------- | -------------------- |
| Rail Corridor     | 50,000   | UIC / ERA 2024       |
| Airport (On-Site) | 25,000   | Airport Ops Proxy    |
| Port              | 40,000   | Port Equipment Proxy |

### 7. Agriculture / Waste / Industry

| Metric              | Value                | Source           |
| ------------------- | -------------------- | ---------------- |
| Cow Methane         | 70–120 kg CH₄/yr     | geo_emissions §3 |
| Model Midpoint Used | 95 kg CH₄/yr         | Midpoint         |
| Waste Methane       | 50–100 kg CH₄ / ton  | geo_emissions §5 |
| Model Midpoint Used | 75 kg CH₄ / ton      | Midpoint         |
| Cement Emission     | 0.9 t CO₂ / t Cement | geo_emissions §4 |

### 8. Carbon Absorption Rates

Units: **kg CO₂ / m² / year**

Source: **IPCC AFOLU / geo_emissions §8**

| Land Type | Absorption |
| --------- | ---------- |
| Forest    | 1.50       |
| Wood      | 1.30       |
| Wetland   | 1.20       |
| Park      | 0.80       |
| Garden    | 0.50       |
| Grass     | 0.30       |

---

## Model Logic

### Building Emissions Formula

$$
E_{thermal} = Area \times EUI \times ThermalShare \times ThermalEF
$$

$$
E_{electric} = Area \times EUI \times ElecShare \times GridEF \times ClimateMultiplier
$$

$$
E_{process} = Operational \times (ProcessMultiplier - 1)
$$

$$
E_{embodied} = Area \times EmbodiedIntensity
$$

$$
E_{total} = E_{thermal} + E_{electric} + E_{process} + E_{embodied}
$$

### Zone Carbon Balance

$$
E_{zone} = Buildings + Transport + Industry + Waste + Livestock
$$

$$
S_{zone} = GreenAreaAbsorption + TreeAbsorption
$$

$$
Balance = S_{zone} - E_{zone}
$$

---

## Emission Model

### Building Emissions

$$
E_{total} = E_{thermal} + E_{electric} + E_{process} + E_{embodied}
$$

#### Thermal Emissions

$$
E_{thermal} = EUI \times Thermal\ Share \times Thermal\ EF \times Area \times Density
$$

#### Electrical Emissions

$$
E_{electric} = EUI \times Electric\ Share \times Grid\ EF \times Climate \times Area \times Density
$$

#### Process Emissions

$$
E_{process} = (Thermal + Electric) \times (Process\ Multiplier - 1)
$$

#### Embodied Carbon

$$
E_{embodied} = Area \times Embodied\ Intensity
$$

### Transport Model

#### Road Emissions

$$
E_{road} = Road\ Area \times Road\ Intensity \times Density\ Multiplier
$$

#### Non-Road Infrastructure

Fixed annual factors per infrastructure unit:

* Rail
* Airport
* Port
* Helipad

### Additional Emission Sources

#### Livestock

$$
Emission = Cattle\ Count \times 95\ kg\ CH_4 \times 28\ GWP
$$

#### Landfill

$$
Emission = Waste\ Tonnes \times 75\ kg\ CH_4 \times 28\ GWP
$$

#### Cement Production

$$
Emission = Cement\ Tonnes \times 0.9\ t\ CO_2/t
$$

---

## Carbon Absorption Model

### Area-Based Absorption

$$
Absorption = Green\ Area \times Land-Type\ Absorption\ Rate
$$

### Tree Absorption

$$
Absorption = Tree\ Count \times 22.5\ kg\ CO_2/tree/year
$$

---

## Output Structure

```python
{
    "zone_metrics": {...},
    "sustainability": {...},
    "benchmark": {...}
}
```

### Zone Metrics

| Field                    | Description                      |
| ------------------------ | -------------------------------- |
| `total_emission_kg_yr`   | Total annual emissions           |
| `total_absorption_kg_yr` | Total annual absorption          |
| `balance_kg_yr`          | Net carbon balance               |
| `balance_ratio`          | Absorption / Emissions           |
| `per_capita_kg_yr`       | Operational emissions per person |
| `intensity_kg_m2_yr`     | Emissions per built m²           |

---

## Sustainability Scoring Logic

### Sustainability Grade (0–100)

#### Weighting

| Component            | Weight |
| -------------------- | ------ |
| Carbon Balance Ratio | 70%    |
| NDVI / Vegetation    | 30%    |

### Benchmark Score (0–100)

#### Weighting

| Component          | Weight |
| ------------------ | ------ |
| Per-Capita Carbon  | 45%    |
| Building Intensity | 25%    |
| Ecology / Balance  | 30%    |

### Grade Thresholds

| Score  | Grade |
| ------ | ----- |
| 85–100 | A     |
| 70–84  | B     |
| 55–69  | C     |
| 40–54  | D     |
| <40    | F     |

---

## Validation Rules

| Validation     | Rule  |
| -------------- | ----- |
| Negative Area  | Error |
| NDVI > 1       | Error |
| Population ≤ 0 | Error |
| Built Area ≤ 0 | Error |
| Occupancy > 24 | Error |

---

## Example Usage

```python
result = analyze_zone(
    buildings=[...],
    green_areas=[...],
    roads=[...],
    country="egypt",
    population=15000,
    built_area=50000,
    ndvi=0.61
)
```

---

## Assumptions / Limitations

### Model Assumptions

1. Building emissions estimated via **floor-area proxy**
2. Road emissions estimated via **road-area proxy**
3. Airport/Port/Rail represent **on-site operations only**
4. Embodied carbon annualized over **50 years**
5. Climate effects simplified into **hot/cold multipliers**
6. NDVI treated as vegetation quality modifier

### Limitations

* Not a replacement for full LCA / audited carbon accounting
* Does not model:
  * Detailed HVAC systems
  * Material-by-material embodied carbon
  * Actual traffic counts
  * Temporal / seasonal variation
  * Building operational telemetry
* Imported goods / supply chain emissions
* Construction transport emissions
* Dynamic traffic simulation
* Hourly HVAC / weather simulation
* Satellite-derived NDVI integration
* Full lifecycle carbon accounting

---

## Recommended Use Cases

### Suitable For

* Comparative urban sustainability analysis
* Development option ranking
* GIS carbon heatmaps
* Academic research
* ESG dashboards

### Not Suitable For

* Legal compliance reporting
* Audited ESG disclosures
* Carbon credit certification
* Engineering-grade simulation

---

## Functional Design Principles

* Pure functional programming
* Stateless architecture
* No side effects
* Deterministic outputs
* No shared mutable state

---

## Future Improvements

1. OSM Polygon Integration
2. Satellite NDVI Raster Integration
3. Dynamic Climate Zone Mapping
4. Building-Type Occupancy Profiles
5. Traffic Volume Based Road Model
6. Weather-Based Energy Modeling
7. Full Lifecycle Assessment Module

---

## Summary

EcoBalance v7.0 is a documentation-grounded geospatial sustainability engine that transforms:

```text
Land Use + Infrastructure + Ecology
```

into:

```text
Carbon Metrics + Sustainability Scores + Benchmark Grades
```

This model is calibrated to produce:

* **Realistic order-of-magnitude urban carbon estimates**
* **Relative sustainability comparisons**
* **Explainable benchmark scoring**
* **Transparent scientific assumptions**

---

## Recommended Citation

If used academically:

```text
EcoBalance Carbon Model v7.0 — Comparative Geospatial Sustainability Engine.
Built using IPCC AR6, IEA 2025, Ember 2023, CRREM 2024,
ScienceDirect Building EUI Review 2023, and geo_emissions.md baseline assumptions.
```

---

## References

### Climate Science / Global Warming Potentials
**IPCC AR6 WGIII Chapter 9 – Buildings**  
https://www.ipcc.ch/report/ar6/wg3/chapter/chapter-9/  
Used for: Building-sector emissions methodology, operational vs embodied emissions framing, heating / building carbon assumptions.

### Global Electricity Grid Factors
**Ember Global Electricity Review 2023**  
https://ember-energy.org/latest-insights/global-electricity-review-2023/  
Used for: Country grid carbon intensities, global average electricity carbon intensity.

### Building Energy Benchmarks / Embodied Carbon
**CRREM Pathways / Building Decarbonization Benchmarks**  
https://www.crrem.org/  
Used for: Sustainable building intensity target, embodied carbon pathway calibration.

### Internal Project Scientific Baseline
**geo_emissions.md**  
Internal project assumptions document used for: Methane / landfill / livestock / tree absorption, cement process emissions, global balance ratios, proxy transport assumptions.

### Additional Sources
* Ember Global Electricity Review 2023
* ScienceDirect Building EUI Review 2023
* IPCC AR6 building archetypes
* OneClickLCA
* SBTi Built Environment Guidance
* EPA Vehicle Emission Factors
* IPCC AFOLU / geo_emissions
