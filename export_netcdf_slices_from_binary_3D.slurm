#!/bin/bash -l
#SBATCH -J R4P50ee
#SBATCH -A cfd135
#SBATCH -p batch
#SBATCH -N 1
#SBATCH -n 1
#SBATCH -c 1
#SBATCH -t 12:00:00
#SBATCH --mem=64G
#SBATCH -o export_%j.out
#SBATCH -e export_%j.err

module load python

cd "$SLURM_SUBMIT_DIR"

echo "===== JOB START ====="
echo "On $(date '+%d %b %Y %H:%M:%S')"
echo "JobID: $SLURM_JOB_ID"
echo "Node: $(hostname)"
echo "====================="

# Save a copy of this script with the job ID for future reference
cp "$0" "$SLURM_SUBMIT_DIR/export_${SLURM_JOB_ID}.slurm"

# Limit all numerical libraries to a single thread to
# avoid hidden multithreading and CPU oversubscription
export OMP_NUM_THREADS=1
export MKL_NUM_THREADS=1
export OPENBLAS_NUM_THREADS=1
export NUMEXPR_NUM_THREADS=1

# Launch the script and time execution
/usr/bin/time -v python export_netcdf_slices_from_binary_3D.py \
  --case R4P50 \
  --planes xz yz \
  --idx_xz 4000 \
  --idx_yz 8000 \
  --vars ee  \
  --nproc 1 \
  --stream \
  --overwrite