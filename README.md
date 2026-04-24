# EcoMeter - Open-Source Location-Based Sustainability Assessment

**EcoMeter** enables users to select any geographic area via map interface, then estimate:

- CO₂ emissions intensity for that region
- Vegetation coverage and estimated oxygen production capacity (Not yet implemented)

## Example Image

![Galala Campus](imgs/preview.svg)

---

## How to install and use

### Part1 Python ENV

For ***NixOS*** based systems

check the [shell](shell.nix) you can run it and have everything you need and sets and activate a uv venv for you

```bash
nix-shell
uv pip install -r requirements.txt
```

For ***non NixOS*** systems you may want to set these environment variables

```bash
# Point uv / pip at the CUDA-aware PyTorch index
export UV_HTTP_TIMEOUT="300"
export UV_EXTRA_INDEX_URL="https://download.pytorch.org/whl/cu121"

export SSL_CERT_DIR=/etc/ssl/certs/
export SSL_CERT_FILE=/etc/ssl/certs/ca-certificates.crt

export NIX_SSL_CERT_FILE=/etc/ssl/certs/ca-certificates.crt

export CURL_CA_BUNDLE=/etc/ssl/certs/ca-certificates.crt
```

then install the requirements:

```bash
uv pip install -r requirements.txt
```

> you may want to set up a venv using uv instead but that's up to you

### part2 downloading the required data manually

as discussed in [overture doc](docs/overture.md) you should download the structures provided inside your location box manually, CHECK IT TO DONWLOAD THAT DATA

Now you are able to run the script

## Problem Statement & Scope

| Aspect | Definition | Implemented status |
|--------|-----------|---------------------|
| **Input** | User selects a geographic bounding box or polygon on an interactive map | No interface yet|
| **Core Question** | *"Is this area's CO₂ output balanced by its natural oxygen production capacity?"* | Half backed still |
| **Output** | Sustainability tier (A–F), visual dashboard, downloadable analysis summary | Not implemented |
| **Academic Scope** | Methodology design, data pipeline architecture - **not production code** | descriptive |
| **Geographic Flexibility** | Any location globally where open satellite/OSM data exists | yet to be implemented |

---

# Licensing

it's an [MIT](LICENSE)
