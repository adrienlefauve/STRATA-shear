# Read Me 
# Adrien Lefauve, 2026

This repository provides a workflow to process, extract, and visualize 3D simulation data of sheared stratified turbulence.

---

## Overview

The pipeline consists of four main stages:

1. **Metadata extraction and organisation**
2. **Parallel extraction of 2D slices from 3D fields**
3. **Automated 2D visualization and figure generation**
4. **3D cube movie generation**

All scripts rely on shared utilities in `utils.py`.

---

## 1. Metadata Extraction

From the original netcdf parameter outputs (13 simulation cases), we generate:

### Outputs

- **Per-case Excel files**
  - Parameters, spectra, diagnostics (multiple tabs per sheet)
  - Useful for human-readable inspection

- **A single aggregated Excel file**
  - Scalar parameters only (one row per case)
  - Includes sanity checks and manual corrections

- **Master CSV file (`params.csv`)**
  - Key parameters only (but even then not all params are used)
  - Used by all downstream Python scripts

---

## 2. Slice Extraction (Parallel)

Scripts:
- `export_slices.py`
- `export_slices.slurm`

### What it does

- Extracts 2D slices from 3D fields stored as Fortran binary files:
  - `u`, `v`, `w`, `r`, `ee`, `chi`
- Planes:
  - `xy`, `xz`, `yz`
- Typically:
  - **5 slices per plane (evenly spaced)**
  - Middle slice included (number 3 of 5)

### Parallelisation

- Tasks = (plane × index × variable)
- ~30 tasks per case for each type of plane xy xz or yz 
- Distributed across 30 cores (typical node has 32)
- xy runs first (fastest), then xz (slower), then yz (slowest) due to non-contiguous memory in the fortran binary files
- Highly efficient (at most a few hours for the largest cases)

### Output

- NetCDF files:
  - one file = one variable + one plane + one index
- Per case:
  - **15 slices × 6 variables = 90 files**

---

## 3. 2D Slice Plotting

Scripts:
- `plot_slices.py` (batch version, best on a compute node with more memory)
- `plot_slices.slurm` (SLURM job script)


### Features

- Reads `params.csv`
- Detects available slices automatically (uses a `cache' pickle file to remember the list of available slices, as on some nodes scanning through the slices took a while)
- Selects slices:
  - default = **middle plane only** 
  - manual override possible

---

### Outputs per case

#### (a) Summary figures

- 3 figures: `xy`, `xz`, `yz` (middle plane by default as per above)
- Each contains all 6 variables
- Low-resolution PNGs

→ **3 figures**

---

#### (b) Full-resolution figures

- 1 figure per variable per plane
- Native resolution:
  - **1 pixel = 1 grid point**
- No interpolation

→ 6 variables × 3 planes = **18 figures**

---

### Total per case

- **21 figures**
- Across 13 cases:
  - **273 figures**

---

## 4. 3D Cube Movies (Parallel)

Scripts:
- `make_cube_image.py` (renders one frame)
- `make_cube_movie.py` (parallel orchestrator + ffmpeg)
- `make_cube_movie.slurm` (SLURM job script)

### What it does

- Renders 3D cube snapshots from the same Fortran binary files as stage 2
- Three orthogonal faces on a half-open box (Plotly `go.Surface`) plus wireframe edges
- Sweeps ("scans") along one axis (`x`, `y`, or `z`) to produce a movie

### Normalisation

Identical to the 2D slice plots:
- `u, v, w` → divided by √Ek
- `r` → converted to buoyancy b'/(N√Ep), using `zAccel = 1000 × Ri` (since dGrad = −0.001 for all cases)
- `ee` → log₁₀(ε / ⟨ε⟩)
- `chi` → log₁₀(χ / ⟨χ⟩), where ⟨χ⟩ = ⟨ε⟩ × Γ₁

All normalisation parameters (`Ri`, `Ek`, `Ep`, `ek`, `ep`, `Gamma1`) are read from `params.csv`.

### Parallelisation

- Each frame is rendered by a separate subprocess (`make_cube_image.py`)
- Distributed across all available cores via `joblib` (typically 32 on Andes)
- Frames are JPGs (smaller than PNGs, no impact on MP4 quality)

### ffmpeg

- Stitches frames into MP4 (H.264)
- Auto-detected: tries system `ffmpeg` first, falls back to `imageio-ffmpeg` bundled binary
- Requires one-time install: `module load python && pip install --user plotly kaleido imageio-ffmpeg`

### Output

- `figures/3D/<case>/<var>_scan<axis>_st<stride>/` — JPG frames + MP4 movie


---

## File Structure (key files)

- `params.csv` → master parameter table
- `utils.py` → shared utilities (I/O, plotting, helpers)

### Slice extraction
- `export_slices.py`
- `export_slices.slurm`

### 2D slice plotting
- `plot_slices.py`
- `plot_slices.slurm`

### 3D cube movies
- `make_cube_image.py` → renders a single 3D cube frame (stateless, called in parallel)
- `make_cube_movie.py` → orchestrates parallel frame rendering + ffmpeg MP4 assembly
- `make_cube_movie.slurm` → SLURM job script for Andes

---

## Key Design Choices

- Separation of **data preparation** and **visualization**
- Use of a **single CSV source of truth**
- **Embarrassingly parallel** slice extraction
- Native-resolution plotting for scientific accuracy

---