#!/bin/bash
#SBATCH -J export_slices
#SBATCH -A cfd135
#SBATCH -p batch
#SBATCH -N 1
#SBATCH -n 1
#SBATCH -c 32
#SBATCH -t 1:00:00
#SBATCH --mem=192G
#SBATCH -o export_%j.out
#SBATCH -e export_%j.err

module load python

export OMP_NUM_THREADS=1
export MKL_NUM_THREADS=1
export OPENBLAS_NUM_THREADS=1
export NUMEXPR_NUM_THREADS=1

# Prefer srun on many systems (propagates Slurm env cleanly)
srun python adrienExportSlicesNetCDFAutoParallel.py \
  --case R1P7 \
  --planes xy xz \
  --stride 1 1 1 \
  --stream \
  --nxy 16 --nxz 16 --nproc 32 \
  --overwrite