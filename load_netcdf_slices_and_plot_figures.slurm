#!/bin/bash
#SBATCH -J fR10P1
#SBATCH -A cfd135
#SBATCH -p batch
#SBATCH -N 1
#SBATCH -n 1
#SBATCH -c 32
#SBATCH -t 2:00:00
#SBATCH --mem=128G
#SBATCH -o export_%j.out
#SBATCH -e export_%j.err

module load python

export OMP_NUM_THREADS=1
export MKL_NUM_THREADS=1
export OPENBLAS_NUM_THREADS=1
export NUMEXPR_NUM_THREADS=1

python load_netcdf_slices_and_plot_figures.py R10P1
