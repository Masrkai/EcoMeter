{ pkgs ? import <nixpkgs> {
    config = {
      allowUnfree = true;
      cudaSupport = true;
    };
  }
}:
let
  # Libraries needed at runtime by PyPI wheels with native extensions
  runtimeLibs = with pkgs; [
    cudaPackages.cudatoolkit
    cudaPackages.cudnn
    stdenv.cc.cc.lib   # libstdc++
    zlib
    libGL
    expat              # ← provides libexpat.so.1
    # If you hit more missing .so errors from rasterio/contextily, also add:
    gdal proj geos libpng libjpeg
  ];
in
pkgs.mkShell {
  name = "Eco";

  buildInputs = with pkgs; [
    python311
    uv
  ] ++ runtimeLibs;

  shellHook = ''
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "  CUDA + uv Nix Shell"
    echo "  CUDA version: $(nvcc --version 2>/dev/null | grep release | awk '{print $5}' | tr -d , || echo 'nvcc not found')"
    echo "  uv   version: $(uv --version)"
    echo "  Python:       $(python --version)"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

    # Create venv with uv if it doesn't exist yet
    if [ ! -d ".venv" ]; then
      echo "→ Creating venv with uv..."
      uv venv .venv --python python3.11
    fi

    # Activate it
    source .venv/bin/activate


    # Point uv / pip at the CUDA-aware PyTorch index
    export UV_HTTP_TIMEOUT="300"
    export UV_EXTRA_INDEX_URL="https://download.pytorch.org/whl/cu121"

    export SSL_CERT_DIR=/etc/ssl/certs/
    export SSL_CERT_FILE=/etc/ssl/certs/ca-certificates.crt

    export NIX_SSL_CERT_FILE=/etc/ssl/certs/ca-certificates.crt

    export CURL_CA_BUNDLE=/etc/ssl/certs/ca-certificates.crt

    # Make Nix libraries visible to dynamically-linked Python extensions
    export LD_LIBRARY_PATH="${pkgs.lib.makeLibraryPath runtimeLibs}:$LD_LIBRARY_PATH"

    echo "→ Venv active: $VIRTUAL_ENV"
  '';
}
