#!/bin/bash -l
#SBATCH -J R1P1cube
#SBATCH -A cfd135
#SBATCH -p batch
#SBATCH -N 1
#SBATCH -n 1
#SBATCH --cpus-per-task=32
#SBATCH --mem=64G
#SBATCH -t 1:00:00
#SBATCH -o cube_movie_%j.out
#SBATCH -e cube_movie_%j.err

# =============================================================================
# Parallel cube-movie maker.
# Edit the USER SETTINGS below, then: sbatch make_cube_movie.slurm
# See make_cube_movie.py for the full tuning guide.
#
# Quick reference (Andes):
#   Quick preview  →  STRIDE=30  SCAN_STRIDE=100  WIDTH=800   FPS=10
#   Publication    →  STRIDE=5   SCAN_STRIDE=10   WIDTH=2000  FPS=20
#
# Memory: peak RAM ≈ (Nx/STRIDE)×(Ny/STRIDE)×(Nz/STRIDE)×4 bytes per worker.
#   R10P7 stride 30 → ~0.6 GB/worker → 32 workers fit easily in 64 GB.
#   R10P7 stride 5  → ~24 GB/worker  → reduce NJOBS or increase --mem.
# =============================================================================

CASE=R1P1
VAR=r                # variable to plot (u v w r ee chi)
STRIDE=2             # downsample the 3D volume by this factor
SCAN=x               # axis to sweep along: x, y, or z
SCAN_STRIDE=20       # step between indices along the scan axis
IX_FRAC=0.0          # fraction of Nx for the fixed x-face (used when SCAN=y or z)
IY_FRAC=0.0          # fraction of Ny for the fixed y-face (used when SCAN=x or z)
IZ_FRAC=0.9          # fraction of Nz for the fixed z-face (used when SCAN=x or y)
FPS=5                # frames per second in the output movie
WIDTH=1000           # image width in pixels
SCALE=1.0            # plotly scale factor (increase for higher-res JPGs)
NO_CBAR=             # non-empty = hide colorbar (shown by default)
NJOBS=32             # parallel workers (match --cpus-per-task)
NO_MOVIE=            # non-empty = skip ffmpeg, only render frames

# ---------------------------------------------------------------------------

module load python
# Requires (once, from a login node):
#   pip install --user plotly kaleido imageio-ffmpeg

cd "$SLURM_SUBMIT_DIR"

echo "======== JOB START ========"
echo "Case:   $CASE"
echo "Var:    $VAR"
echo "Scan:   $SCAN (stride $SCAN_STRIDE)"
echo "Node:   $(hostname)"
echo "JobID:  $SLURM_JOB_ID"
echo "Date:   $(date '+%d %b %Y %H:%M:%S')"
echo "==========================="
echo ""

cp "$0" "${SLURM_SUBMIT_DIR}/cube_movie_${SLURM_JOB_ID}.slurm"

export OMP_NUM_THREADS=1
export MKL_NUM_THREADS=1
export OPENBLAS_NUM_THREADS=1
export NUMEXPR_NUM_THREADS=1

python make_cube_movie.py \
    --case         "$CASE"        \
    --var          "$VAR"         \
    --stride       "$STRIDE"      \
    --scan         "$SCAN"        \
    --scan-stride  "$SCAN_STRIDE" \
    --ix-frac      "$IX_FRAC"     \
    --iy-frac      "$IY_FRAC"     \
    --iz-frac      "$IZ_FRAC"     \
    --fps          "$FPS"         \
    --width        "$WIDTH"       \
    --scale        "$SCALE"       \
    --njobs        "$NJOBS"       \
    ${NO_CBAR:+--no-cbar}             \
    ${NO_MOVIE:+--no-movie}

echo ""
echo "=========== JOB END ==========="
echo "$(date '+%d %b %Y %H:%M:%S')"
echo "==============================="
