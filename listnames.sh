#!/bin/bash

ROOT="/lustre/orion/cfd135/proj-shared/Hsst"

cases=(
  R1P1 R1P7 R1P50
  R4P1 R4P7 R4P50
  R6P1 R6P7 R6P50
  R8P1 R8P7
  R10P1 R10P7
)

for case in "${cases[@]}"; do
  dir="$ROOT/$case/001_Final"
  find "$dir" -maxdepth 1 -type f \
    \( -name 'u_*' -o -name 'v_*' -o -name 'w_*' -o -name 'r_*' -o -name 'ee_*' -o -name 'chi_*' \) \
    -printf '%f\n'
done