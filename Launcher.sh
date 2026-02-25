#!/usr/bin/env bash
set -e

echo ""
echo " ============================================="
echo "   A1D VIDEO UPSCALER v2"
echo "   Powered by SotongHD Architecture"
echo " ============================================="
echo ""

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Check Python
if ! command -v python3 &>/dev/null; then
    echo "[ERROR] Python3 tidak ditemukan. Install Python 3.10+ terlebih dahulu."
    exit 1
fi

PYTHON_VER=$(python3 -c "import sys; print(sys.version_info.minor)")
if [ "$PYTHON_VER" -lt 10 ]; then
    echo "[WARN] Python 3.10+ direkomendasikan. Versi kamu mungkin kurang kompatibel."
fi

echo "[INFO] Menginstall dependencies..."
python3 -m pip install -r requirements.txt --quiet

echo "[INFO] Memulai aplikasi..."
python3 main.py
