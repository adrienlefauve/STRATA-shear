#!/bin/bash -l
#SBATCH -J R4P50f
#SBATCH -A cfd135
#SBATCH -p batch
#SBATCH -N 1
#SBATCH -n 1
#SBATCH -c 1
#SBATCH -t 1:00:00
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

# Launch the script and time execution
/usr/bin/time -v python load_netcdf_slices_and_plot_figures.py R4P50
