#!/bin/bash -l
#SBATCH -J R10P7fig
#SBATCH -A cfd135
#SBATCH -p batch
#SBATCH -N 1
#SBATCH -n 1
#SBATCH -c 1          # sequential script — only 1 CPU needed
#SBATCH -t 2:00:00
#SBATCH --mem=32G     # can stay low (a few GB) as it only reads one lightweight NetCDF slice at a time, not the full binary volumes
#SBATCH -o plot_slices_%j.out
#SBATCH -e plot_slices_%j.err

# =============================================================================
# 2D slice figure exporter — reads exported NetCDF slices and writes figures
# Edit the USER SETTINGS below, then: sbatch plot_slices.slurm
# See plot_slices.py for full details.
# =============================================================================

CASE=R10P7

# --- Slice selection (default: slice nearest to mid-plane) ---
IDX_XY=""    # explicit z-index for xy plane, e.g. IDX_XY=512.  Leave blank for auto.
IDX_XZ=""    # explicit y-index for xz plane.  Leave blank for auto.
IDX_YZ=""    # explicit x-index for yz plane.  Leave blank for auto.

# --- Output control ---
SKIP_SUMMARY=""   # set to 1 to skip the 3 summary figures (one per plane)
SKIP_NATIVE=""    # set to 1 to skip the native-resolution per-variable figures
REFRESH_CACHE=1  # set to 1 to ignore the cached slice-file list and rescan the directory

# --- Paths (leave blank to use defaults from plot_slices.py) ---
OUTDIR=""         # output directory for figures. Default: <code-root>/figures/<case>

# ---------------------------------------------------------------------------

module load python

cd "$SLURM_SUBMIT_DIR"

echo "======== JOB START ========"
echo "Case:  $CASE"
echo "Node:  $(hostname)"
echo "JobID: $SLURM_JOB_ID"
echo "Date:  $(date '+%d %b %Y %H:%M:%S')"
echo "==========================="
echo ""

# Save a copy of this script for reproducibility
cp "$0" "${SLURM_SUBMIT_DIR}/plot_slices_${SLURM_JOB_ID}.slurm"

/usr/bin/time -v python plot_slices.py "$CASE"          \
    ${IDX_XY:+--idx-xy "$IDX_XY"}                      \
    ${IDX_XZ:+--idx-xz "$IDX_XZ"}                      \
    ${IDX_YZ:+--idx-yz "$IDX_YZ"}                      \
    ${SKIP_SUMMARY:+--skip-summary}                     \
    ${SKIP_NATIVE:+--skip-native}                       \
    ${REFRESH_CACHE:+--refresh-cache}                   \
    ${OUTDIR:+--outdir "$OUTDIR"}

echo ""
echo "=========== JOB END ==========="
echo "$(date '+%d %b %Y %H:%M:%S')"
echo "==============================="