#!/bin/bash
#SBATCH --account cfd135
#SBATCH -J cubeMovie
#SBATCH -o R-%x.%j.out
#SBATCH -e R-%x.%j.err
#SBATCH -N 1
#SBATCH -t 5:00:00
#SBATCH --cpus-per-task=16

module purge
module load python

# Make conda available in non-interactive shell
source "$(conda info --base)/etc/profile.d/conda.sh"
conda activate andes1

# Avoid oversubscription
export OMP_NUM_THREADS=1
export MKL_NUM_THREADS=1
export OPENBLAS_NUM_THREADS=1
export NUMEXPR_NUM_THREADS=1

# Go to where you submitted the job from
cd "$SLURM_SUBMIT_DIR"

# Debug: confirm interpreter in the .out file
echo "which python: $(which python)"
python -c "import sys; print('sys.executable:', sys.executable)"

# IMPORTANT: run wrapper with the env python explicitly
ENV_PY="$HOME/.conda/envs/andes1/bin/python"

"$ENV_PY" adrienMakeCubeMovieParallel.py \
  --case R1P7 \
  --var r \
  --stride 5 \
  --ixstride 20 \
  --fps 5 \
  --cbar \
  --width 1000 \
  --njobs 16