#!/bin/bash
#SBATCH -J R8P7
#SBATCH -A cfd135
#SBATCH -p batch
#SBATCH -N 1
#SBATCH -n 1
#SBATCH -c 32
#SBATCH -t 20:00:00
#SBATCH --mem=128G
#SBATCH -o export_%j.out
#SBATCH -e export_%j.err

module load python

export OMP_NUM_THREADS=1
export MKL_NUM_THREADS=1
export OPENBLAS_NUM_THREADS=1
export NUMEXPR_NUM_THREADS=1


# Prefer srun on many systems 
python export_netcdf_slices_from_binary_3D.py \
  --case R8P7 --planes yz --nyz 5 \
  --vars u v w r ee chi \
  --nproc 30 --stream --overwrite
