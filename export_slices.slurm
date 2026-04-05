#!/bin/bash -l
#SBATCH -J R10P7yz
#SBATCH -A cfd135
#SBATCH -p batch
#SBATCH -N 1
#SBATCH -n 1
#SBATCH -c 2
#SBATCH --mem=220G
#SBATCH -t 24:00:00
#SBATCH -o export_slices_%j.out
#SBATCH -e export_slices_%j.err

# =============================================================================
# Unified 2D slice exporter — xy, xz, yz
# Edit the USER SETTINGS below, then: sbatch export_slices.slurm
# See export_slices.py for the full tuning guide.
#
# Quick reference (Andes):
#   xy / xz  →  -c <n_tasks>  --mem=32G   -t 4:00:00   (n_tasks = n_planes×n_slices×n_vars)
#   yz       →  -c 2          --mem=220G  -t 24:00:00  (set NPROC=2 below)
# =============================================================================

CASE=R10P7
PLANES="yz"          # e.g. "xy xz yz" or just "yz"
VARS="u v w r ee chi"
NXY=0                # number of xy slices, evenly spaced in z (0 = skip)
NXZ=0                # number of xz slices, evenly spaced in y (0 = skip)
NYZ=5                # number of yz slices, evenly spaced in x (0 = skip)
IDX_XY=""            # explicit z-index(es) for xy, e.g. IDX_XY="100 200 300". Overrides NXY.
IDX_XZ=""            # explicit y-index(es) for xz, e.g. IDX_XZ="500 1000". Overrides NXZ.
IDX_YZ=""            # explicit x-index(es) for yz, e.g. IDX_YZ="1000 8000 15840". Overrides NYZ.
                     # Leave all IDX_* blank to use the N** counts above.
STRIDE="1 1 1"       # (sx, sy, sz) — subsample along x, y, z in the output slice.
                     # 1 1 1 = full resolution (recommended for archival).
                     # For yz planes, sx is IGNORED; only sy sz matter (e.g. "1 2 2").
NPROC=2              # number of parallel workers. Leave blank for auto.
                     # yz: auto = avail_RAM // 50 GB (e.g. 220G → 3 workers × 66 GB).
                     # Set NPROC=2 to force 2 workers × ~99 GB — fastest on Andes.

# ---------------------------------------------------------------------------

module load python

cd "$SLURM_SUBMIT_DIR"

echo "======== JOB START ========"
echo "Case:   $CASE"
echo "Planes: $PLANES"
echo "Node:   $(hostname)"
echo "JobID:  $SLURM_JOB_ID"
echo "Date:   $(date '+%d %b %Y %H:%M:%S')"
echo "==========================="
echo ""

# Save a copy of this script for reproducibility
cp "$0" "${SLURM_SUBMIT_DIR}/export_${CASE}_${SLURM_JOB_ID}.slurm"

# Prevent hidden multithreading from NumPy/BLAS competing with our workers
export OMP_NUM_THREADS=1
export MKL_NUM_THREADS=1
export OPENBLAS_NUM_THREADS=1
export NUMEXPR_NUM_THREADS=1

/usr/bin/time -v python export_slices.py \
    --case    "$CASE"                   \
    --planes  $PLANES                   \
    --vars    $VARS                     \
    --nxy     "$NXY"                    \
    --nxz     "$NXZ"                    \
    --nyz     "$NYZ"                    \
    --stride  $STRIDE                   \
    ${NPROC:+--nproc "$NPROC"}          \
    ${IDX_XY:+--idx_xy $IDX_XY}       \
    ${IDX_XZ:+--idx_xz $IDX_XZ}       \
    ${IDX_YZ:+--idx_yz $IDX_YZ}

echo ""
echo "=========== JOB END ==========="
echo "$(date '+%d %b %Y %H:%M:%S')"
echo "==============================="