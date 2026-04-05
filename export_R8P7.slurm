#!/bin/bash -l
#SBATCH -J export_R8P7
#SBATCH -A cfd135
#SBATCH -p batch
#SBATCH -N 1
#SBATCH -n 1
#SBATCH -c 30                  # enough CPUs for Phase 1 (nproc=30)
#SBATCH --mem=128G             # needed for Phase 2 yz slab reader
#SBATCH -t 6:00:00
#SBATCH -o export_R8P7_%j.out
#SBATCH -e export_R8P7_%j.err

# =============================================================================
# R8P7 full 2D-slice export
#   Phase 1 — xy + xz   (fast, parallel, ~30 min)
#   Phase 2 — yz         (heavy sequential I/O, one file-pass per variable)
#
# R8P7 grid:  Nx=23040  Ny=11520  Nz=5760
# File size per variable: ~5.7 TB  (Fortran-order float32)
# yz slab size @ 18 GB budget: ~18 GB / 1.01 GB per z-plane = ~17 z-planes
#
# Memory budget (Phase 2):
#   6 workers × 18 GB slab  +  6 × ~1.3 GB output  ≈  116 GB     ≤ 128 GB  ✓
#
# Adjust these if needed:
#   NSLICES  — number of evenly-spaced slices per plane
#   NPROC_1  — workers for Phase 1 (xy+xz),  recommendation: ~30
#   NPROC_2  — workers for Phase 2 (yz),      recommendation: 6
#   CHUNK_GB — RAM per yz worker (GB),         recommendation: floor(128/NPROC_2) - 2
# =============================================================================

CASE=R8P7
NSLICES=5
NPROC_1=30
NPROC_2=6
CHUNK_GB=18

# ---------------------------------------------------------------------------

module load python

cd "$SLURM_SUBMIT_DIR"

echo "===== JOB START ====="
echo "Case:   $CASE"
echo "Node:   $(hostname)"
echo "JobID:  $SLURM_JOB_ID"
echo "Date:   $(date '+%d %b %Y %H:%M:%S')"
echo "====================="
echo ""

# Save a copy of this script for reproducibility
cp "$0" "${SLURM_SUBMIT_DIR}/export_${CASE}_${SLURM_JOB_ID}.slurm"

# Prevent hidden multithreading from NumPy/BLAS competing with our workers
export OMP_NUM_THREADS=1
export MKL_NUM_THREADS=1
export OPENBLAS_NUM_THREADS=1
export NUMEXPR_NUM_THREADS=1

# ---------------------------------------------------------------------------
# Phase 1 — xy and xz planes
#   I/O pattern: contiguous or near-contiguous  →  fast even at large Nx
#   Parallelism: one task per (var, plane, slice)  →  30 tasks with NSLICES=5
# ---------------------------------------------------------------------------

echo "===== Phase 1: xy + xz ====="
echo "Started: $(date '+%H:%M:%S')"
echo ""

/usr/bin/time -v python export_netcdf_slices_from_binary_3D.py \
    --case    "$CASE"          \
    --planes  xy xz            \
    --nxy     "$NSLICES"       \
    --nxz     "$NSLICES"       \
    --vars    u v w r ee chi   \
    --nproc   "$NPROC_1"       \
    --stream                   \
    --overwrite

echo ""
echo "Phase 1 done: $(date '+%H:%M:%S')"
echo ""

# ---------------------------------------------------------------------------
# Phase 2 — yz plane
#   I/O pattern: fully strided in Fortran-order files  →  requires slab reader
#   Each worker reads its variable file exactly ONCE regardless of NSLICES
#   (uses slice2d_multi_yz internally).
#
#   Peak RAM: NPROC_2 × CHUNK_GB + small output buffers
#     6 × 18 = 108 GB + ~8 GB output  ≈  116 GB  (safe on 128 GB node)
#
#   To export more slices without extra I/O cost, increase NSLICES freely.
# ---------------------------------------------------------------------------

echo "===== Phase 2: yz (heavy) ====="
echo "Started: $(date '+%H:%M:%S')"
echo ""

/usr/bin/time -v python export_yz_heavy.py \
    --case             "$CASE"        \
    --nyz              "$NSLICES"     \
    --vars             u v w r ee chi \
    --nproc            "$NPROC_2"     \
    --yz-chunk-mem-gb  "$CHUNK_GB"    \
    --stride           1 1 1          \
    --overwrite

echo ""
echo "Phase 2 done: $(date '+%H:%M:%S')"
echo ""
echo "===== JOB END ====="
echo "$(date '+%d %b %Y %H:%M:%S')"
