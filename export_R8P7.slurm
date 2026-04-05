#!/bin/bash -l
#SBATCH -J export_R8P7_yz
#SBATCH -A cfd135
#SBATCH -p batch
#SBATCH -N 1
#SBATCH -n 1
#SBATCH -c 6                   # one core per yz worker
#SBATCH --mem=220G
#SBATCH -t 6:00:00
#SBATCH -o export_R8P7_yz_%j.out
#SBATCH -e export_R8P7_yz_%j.err

# =============================================================================
# R8P7 — yz slice export only (xy+xz already done)
#
# R8P7 grid:  Nx=23040  Ny=11520  Nz=5760
# File size per variable: ~5.7 TB  (Fortran-order float32)
#
# Memory budget (220 GB allocated):
#   6 workers x 34 GB slab  +  6 x 0.25 GB output  ~  206 GB  <=  220 GB  ok
#   one z-plane = (Nx+2)*Ny*4 = 23042*11520*4 ~ 1.01 GB
#   chunk_nz = floor(34 GB / 1.01 GB) = 33 z-planes per slab
#
# NSLICES=1  -> one yz slice at mid-x (test run)
# Once confirmed, change to NSLICES=5 for the full export
# =============================================================================

CASE=R8P7
NSLICES=1      # change to 5 for full export once test passes
NPROC=6
CHUNK_GB=34

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
cp "$0" "${SLURM_SUBMIT_DIR}/export_${CASE}_yz_${SLURM_JOB_ID}.slurm"

# Prevent hidden multithreading from NumPy/BLAS competing with our workers
export OMP_NUM_THREADS=1
export MKL_NUM_THREADS=1
export OPENBLAS_NUM_THREADS=1
export NUMEXPR_NUM_THREADS=1

# ---------------------------------------------------------------------------
# yz plane — slab-based sequential reader
#   Each worker reads its variable file exactly ONCE regardless of NSLICES.
#   6 variables processed in parallel (one per worker).
# ---------------------------------------------------------------------------

echo "===== yz export ====="
echo "Started: $(date '+%H:%M:%S')"
echo ""

/usr/bin/time -v python export_yz_heavy.py \
    --case             "$CASE"        \
    --nyz              "$NSLICES"     \
    --vars             u v w r ee chi \
    --nproc            "$NPROC"       \
    --yz-chunk-mem-gb  "$CHUNK_GB"    \
    --stride           1 1 1          \
    --overwrite

echo ""
echo "yz export done: $(date '+%H:%M:%S')"
echo ""
echo "===== JOB END ====="
echo "$(date '+%d %b %Y %H:%M:%S')"
