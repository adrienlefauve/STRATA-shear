#!/bin/bash
#SBATCH --account cfd135
#SBATCH -J mkSl
#SBATCH -o R-%x.%j.out
#SBATCH -e R-%x.%j.err
#SBATCH -N 1
#SBATCH -t 10:00:00

module load python

source activate andes1

python plotSlices.py