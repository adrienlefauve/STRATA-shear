# Read Me 
# Adrien Lefauve, 2026

This repository provides a workflow to process, extract, and visualize 3D simulation data of sheared stratified turbulence.

---

## Overview

The pipeline consists of three main stages:

1. **Metadata extraction and organisation**
2. **Parallel extraction of 2D slices from 3D fields**
3. **Automated visualization and figure generation**

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

Script:
- `export_netcdf_slices_from_binary_3D.py`
- `export_netcdf_slices_from_binary_3D.slurm`

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

## 3. Visualization & Plotting

Scripts:
- `load_netcdf_slices_and_plot_figures.ipynb` (interactive, fine for the lighter cases not needed much memory)
- `load_netcdf_slices_and_plot_figures.py` (batch version for the heavier cases, best on a compute node with more memory)
- `load_netcdf_slices_and_plot_figures.slurm` to launch the .py script


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

## File Structure (key files)

- `params.csv` → master parameter table
- `utils.py` → shared utilities (I/O, plotting, helpers)

### Slice extraction
- `export_netcdf_slices_from_binary_3D.py`
- `export_netcdf_slices_from_binary_3D.slurm`

### Plotting
- `load_netcdf_slices_and_plot_figures.py`
- `load_netcdf_slices_and_plot_figures.ipynb`
- `load_netcdf_slices_and_plot_figures.slurm`

---

## Key Design Choices

- Separation of **data preparation** and **visualization**
- Use of a **single CSV source of truth**
- **Embarrassingly parallel** slice extraction
- Native-resolution plotting for scientific accuracy

---