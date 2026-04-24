# Location Mapping Standards: Complete Reference Guide

**Example Location:** Eiffel Tower, Paris, France
**WGS84 Decimal Degrees:** 48.85837° N, 2.294481° E

---

## Master Reference Table

| Standard                          | Format & Structure       | Example (Eiffel Tower)            | Primary Use                               | Typical Precision    |
|-----------------------------------|--------------------------|-----------------------------------|-------------------------------------------|----------------------|
| **Decimal Degrees (DD)**          | `±DD.DDDDD°` (lat, lon)  | 48.85837° N, 2.294481° E          | Web maps, databases, APIs                 | ~1.1 m at 5 decimals |
| **Degrees Minutes Seconds (DMS)** | `DDD° MM' SS.S" H`       | 48° 51′ 30.13″ N, 2° 17′ 40.13″ E | Nautical charts, aviation, legal deeds    | ~0.3 m at 0.01″      |
| **Degrees Decimal Minutes (DDM)** | `DDD° MM.MMM′ H`         | 48° 51.502′ N, 2° 17.669′ E       | Marine GPS, handheld receivers            | ~1.8 m at 3 dec. min |
| **UTM**                           | `Zone Band E N` (meters) | 31U 448251 m E, 5411952 m N       | Military, scientific, topographic mapping | 1 m                  |
| **MGRS (Military)**               | `ZBLL EEEEE NNNNN`       | 31UDQ 48250 11952                 | NATO / US DoD standard                    | 1 m                  |
| **USNG**                          | `ZB LL EEEEE NNNNN`      | 31U DQ 48250 11952                | US emergency response (FEMA)              | 1 m                  |
| **What3Words**                    | `word.word.word`         | `sifts.bottled.develop`           | Human-readable addressing                 | ~3 m                 |
| **Plus Code (OLC)**               | `CCCCCCCC+CC`            | `8FW4V75V+8Q`                     | Offline sharing, addressing               | ~14 m                |
| **Geohash**                       | `base32 string`          | `u09tunqu9`                       | Databases, geospatial indexing            | ~2.4 m (9 chars)     |
| **Maidenhead (QTH)**              | `FFSSBBXX`               | `JN18DU56`                        | Amateur radio, antenna pointing           | ~4.6 m (8 chars)     |
| **NAC**                           | `XXXXXX XXXXXX`          | `H5Q2KG R48QMX`                   | Universal geographic encoding             | ~1 m                 |

---

## Detailed Standard Explanations

### 1. Decimal Degrees (DD)

The simplest and most common machine-readable format. Latitude ranges from −90° to +90°; longitude from −180° to +180°. Positive values indicate North and East; negative indicates South and West. It is the native format for Google Maps, GeoJSON, and most REST APIs.

### 2. Degrees Minutes Seconds (DMS)

A sexagesimal system dividing each degree into 60 minutes and each minute into 60 seconds. It is the traditional standard for maritime and aeronautical navigation because it aligns with sextant measurements . The format is unambiguous but verbose for data entry.

### 3. Degrees Decimal Minutes (DDM)

A hybrid used by many Garmin and marine GPS units. The degree component is integer, while the minute component carries the fractional precision. One decimal minute equals about 1.85 km at the equator; three decimals yield roughly 1.8 m precision.

### 4. Universal Transverse Mercator (UTM)

The world is divided into 60 longitudinal zones (each 6° wide) and 20 latitudinal bands (C–X, omitting I and O). Paris lies in **Zone 31U**. Coordinates are expressed as easting (distance in meters east from the zone’s central meridian) and northing (distance in meters from the equator) . UTM avoids the ambiguity of latitude/longitude order and provides a consistent metric grid for distance and area calculations.

### 5. Military Grid Reference System (MGRS)

The NATO standard derived from UTM . An MGRS string consists of:

- **Grid Zone Designator (GZD):** `31U` (zone + band)
- **100 km Square Identification:** `DQ` (a pair of letters locating the 100 km × 100 km square)
- **Numerical location:** `48250 11952` (easting and northing *within* the 100 km square, using only the last 5 digits of the full UTM value)

MGRS describes either a point or a grid cell depending on how many digits are provided (2–10 digits total).

### 6. United States National Grid (USNG)

Functionally identical to MGRS in its alphanumeric notation but formatted with spaces for readability: `31U DQ 48250 11952` . FEMA Directive 092-5 mandates USNG as the standard geographic reference for US land-based emergency operations.

### 7. What3Words (W3W)

A proprietary system that divides the world into 3 m × 3 m squares and assigns each a unique three-word address. It is designed for human communication in areas without street addresses. Conversion requires the What3Words API or app; there is no open mathematical formula .

### 8. Plus Code (Open Location Code)

Developed by Google, Plus Codes encode latitude and longitude in a base-20 alphanumeric string. The first four characters define a 1° × 1° area; the next four narrow it to ~14 m; the final two after the `+` provide ~14 m precision. A **short code** (e.g., `V75V+8Q Paris`) can replace the first four characters with a locality name .

### 9. Geohash

An open-source geocoding system using base-32 character strings. It works by recursively bisecting latitude and longitude ranges, alternating between the two axes with each character. Because it is a Z-order curve, nearby locations usually share similar prefixes, making it ideal for spatial indexing in databases.

### 10. Maidenhead Locator (QTH)

Used by amateur radio operators. The world is divided into:

- **Fields:** 18×18 (20° lon × 10° lat) — letters AA–RR
- **Squares:** 10×10 within each field (2° × 1°) — digits 00–99
- **Sub-squares:** 24×24 (5′ × 2.5′) — letters aa–xx
- **Extended:** 10×10 further subdivisions — digits 00–99

An 8-character locator (`JN18DU56`) provides sufficient precision for antenna beam headings.

### 11. Natural Area Coding (NAC)

Uses a base-30 character set (0–9 and consonants, excluding vowels to avoid accidental word formation). The world is encoded into two strings: one for longitude and one for latitude. A 6-character NAC component yields ~1 m precision .

---

## Conversion Methods: From Any Format to All Others

### From Decimal Degrees (the universal pivot)

Because most libraries and algorithms accept DD as input, converting **to** DD is the critical first step.

| Target         | Formula / Method                                                                                                                                                        |
|----------------|-------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| **DMS**        | `Degrees = int(DD)`; `Minutes = int((DD − Degrees) × 60)`; `Seconds = ((DD − Degrees) × 60 − Minutes) × 60`                                                             |
| **DDM**        | `Degrees = int(DD)`; `Decimal Minutes = (DD − Degrees) × 60`                                                                                                            |
| **UTM**        | Apply the Transverse Mercator projection for the target zone. Use libraries such as **pyproj**, **Proj4js**, or online converters. There is no simple hand formula.     |
| **MGRS**       | 1. Convert DD → UTM. 2. Determine the 100 km square ID from the UTM easting/northing. 3. Truncate the UTM values to 5-digit offsets within that square.                 |
| **Geohash**    | Recursive bisection: alternate between longitude and latitude, dividing the range in half and appending the base-32 index (0–9, b–z excluding a, i, l, o) at each step. |
| **Maidenhead** | `FieldLon = int((Lon+180)/20)`; `FieldLat = int((Lat+90)/10)`; repeat for squares, subs, and extended digits using successive division by 2°, 1°, 5′, 2.5′, etc.        |
| **Plus Code**  | Recursive base-20 encoding in 2.5° × 2.5° tiles. Use the **Google Open Location Code** library.                                                                         |
| **W3W**        | Requires API call to What3Words (proprietary).                                                                                                                          |
| **NAC**        | Proprietary base-30 recursive subdivision. Use the NAC geographic encoding library.                                                                                     |

### From DMS → DD

`DD = Degrees + (Minutes / 60) + (Seconds / 3600)`
Apply negative sign for South or West.

### From DDM → DD

`DD = Degrees + (Decimal Minutes / 60)`
Apply negative sign for South or West.

### From UTM → DD

Reverse the Transverse Mercator projection for the specified zone. Libraries are strongly recommended because the inverse formulas involve series expansions and ellipsoid parameters.

### From MGRS → UTM → DD

1. Extract the GZD (`31U`) to know the zone and band.
2. Use the 100 km square ID (`DQ`) to determine the base easting and northing (e.g., 400000 m E, 5400000 m N).
3. Append the 5-digit offsets: `Easting = 400000 + 48250`; `Northing = 5400000 + 11952`.
4. Convert the resulting UTM coordinates to DD.

### From Geohash → DD

Decode each base-32 character back to its 5-bit value. Rebuild the binary fraction by alternating longitude/latitude bits, then map the final binary fraction back to the degree range [−180, 180] and [−90, 90].

### Practical Recommendation

For bulk or programmatic conversion, use **pyproj** (Python), **Proj4** (C/C++), or **geographiclib**. These handle the ellipsoidal math for UTM, MGRS, and DD accurately. For Geohash, Maidenhead, and Plus Codes, open-source libraries exist in most languages. What3Words and NAC require vendor APIs or specific SDKs.
