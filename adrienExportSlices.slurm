#!/bin/bash
#SBATCH -J export_R6P50_slices
#SBATCH -A cfd135            # your project
#SBATCH -p batch             # standard compute partition
#SBATCH -N 1
#SBATCH -n 1                 # single task
#SBATCH -c 1                 # single core (I/O-bound)
#SBATCH -t 18:00:00          # adjust as needed
#SBATCH --mem=8G             # modest memory
#SBATCH -o export_%j.out
#SBATCH -e export_%j.err

# --- environment ---
module load python

# optional but recommended
export OMP_NUM_THREADS=1

# --- run ---
python adrienAutoExportSlicesNetCDF.py \
  --case R8P1 \
  --planes yz \
  --stride 1 1 1 \
  --stream \
  --overwrite
