# STRATA-shear

Post-processing and visualisation pipeline for the SHASSST direct numerical simulations
of statistically stationary, homogeneous, sheared, stably stratified turbulence.

The pipeline turns very large 3D DNS outputs into 2D NetCDF slices, summary and
native-resolution PNG figures, MP4 cube movies, and a browsable web viewer.

Adrien Lefauve, Miles M. P. Couchman, Stephen M. de Bruyn Kops, 2026

> **Data deposit (Constellation):** *(to be added once the deposit is live)*

See STRATA research group website for further context and datasets

STRATA - Supercomputing for Stratified Turbulence Research Advancing Theory and Application

https://stratified-turbulence.github.io/web/

---

## Pipeline overview

The repository is organised around five stages. Each is independently runnable
once its inputs are available.

| # | Stage | Script(s) | Reads | Produces |
| - | ----- | --------- | ----- | -------- |
| 1 | Metadata extraction | `inspect_params.ipynb` | per-case parameter NetCDFs `<CASE>.nc` | per-case and aggregated `.xlsx` |
| 2 | 2D slice extraction | `export_slices.py` (+ `.slurm`) | raw Fortran 3D binaries | NetCDF 2D slices |
| 3 | 2D slice plotting | `plot_slices.py` (+ `.slurm`), `plot_slices.ipynb` | the NetCDF 2D slices | summary + native-resolution PNGs |
| 4 | 3D cube movies | `make_cube_movie.py` (+ `.slurm`), `make_cube_image.py` | raw Fortran 3D binaries | per-case JPG frames + MP4 movies |
| 5 | Web viewer | `viewer/tile_images.py`, `viewer/gen_*_manifest.py`, `viewer/*/index.html` | rendered PNGs + MP4s | DZI tile pyramids + HTML viewers |

`utils.py` holds shared utilities (binary IO, lazy fields, normalisations, plotting helpers).

`params.csv` is the single source of truth for per-case parameters 
(`Ri`, `Ek`, `Ep`, `eps`, `Gamma1`, `Nx`, `Lx`, …) and is read by every stage 2–4 script.

---

## Quick start

```bash
git clone https://github.com/adrienlefauve/strata-shear.git
cd strata-shear

# Per-machine paths (see "Local configuration" below)
cp local_config.py.example local_config.py
$EDITOR local_config.py

# Python deps (use a venv or conda env if you prefer)
pip install -r requirements.txt   # or install the packages listed below
```

Minimal Python dependencies (used across all stages):

```
numpy
scipy
pandas
matplotlib
psutil
Pillow
joblib
netCDF4
h5py
plotly
kaleido
imageio-ffmpeg
openpyxl              # only for stage 1 (.xlsx export)
pyvips                # only for stage 5 viewer (also: brew install vips)
```

System tools (only for stage 5): `vips`, `ffmpeg` (or `imageio-ffmpeg`'s bundled
binary), and optionally `rclone` to upload to Cloudflare R2.

---

## Local configuration

Each script reads file-system paths from an optional `local_config.py` at the
repo root. The file is git-ignored, so your real paths never leave your
machine. If `local_config.py` is missing, every path can still be passed via
CLI flags.

`local_config.py.example` lists the variables and is the file you copy to
`local_config.py` and edit.

```python
# local_config.py
from pathlib import Path

PROJECT_ROOT = Path("/lustre/orion/cfd135/proj-shared/Hsst")  # stage 1, 2, 4
CODE_ROOT    = Path(__file__).resolve().parent                # stage 3
SNAPSHOTS    = Path("/path/to/your/snapshots")                # stage 5
MOVIES       = Path("/path/to/your/cube-movies")              # stage 5
```

### Three realistic setups

**A. Running on Andes/Frontier (where the simulations live):**

```python
PROJECT_ROOT = Path("/lustre/orion/cfd135/proj-shared/Hsst")
CODE_ROOT    = Path("/ccs/home/<your-username>/git/strata-shear")
# SNAPSHOTS / MOVIES not needed here
```

All five stages are runnable. Use the SLURM scripts for the heavy ones.

**B. Running on a workstation with the Constellation deposit unpacked:**

```python
PROJECT_ROOT = Path("/Volumes/MyDrive/STRATA-deposit/cases")
CODE_ROOT    = Path(__file__).resolve().parent
SNAPSHOTS    = Path("/Volumes/MyDrive/STRATA-deposit/snapshots")
MOVIES       = Path("/Volumes/MyDrive/STRATA-deposit/cube-movies")
```

The deposit contains everything the scripts need:

- raw Fortran binaries → stage 2 and stage 4 work
- per-case `.nc` parameter files → stage 1 works
- exported 2D NetCDF slices → stage 3 works without re-running stage 2
- rendered PNGs + MP4s → stage 5 works without re-running stages 3 and 4

**C. Just want to look at the data, not re-run anything:**

Skip `local_config.py` entirely. Open the offline viewer zip from the
Constellation deposit and double-click `index.html` (see `viewer/readme.md`).

---

## Stage 1 — Metadata extraction

Each simulation case has a parameter NetCDF at
`<PROJECT_ROOT>/<CASE>/001_Final/<CASE>.nc` containing scalar parameters,
3D-averaged diagnostics, and 1D spectra.

`inspect_params.ipynb` opens each `<CASE>.nc`, exports a per-case Excel
workbook (one sheet per group: scalars, diagnostics, spectra) with instantaneous
and time average values, and an aggregated Excel workbook with all the time averages

---

## Stage 2 — 2D slice extraction (parallel, SLURM)

`export_slices.py` reads the raw Fortran-order float32 binary files for one
case and writes 2D NetCDF slices for the variables `u, v, w, r, ee, chi`,
along the planes `xy`, `xz`, `yz`.

### Slice counts in the deposit

We exported **5 evenly-spaced slices per plane** (mid-plane plus four off-axis)
for every case, except `R10P7` which has only **1 `yz` slice** (the
non-contiguous Fortran read for a yz slice on the largest grid is very 
slow even on a full Andes node).

Per-case output therefore is:

| Case | xy | xz | yz | Total slices | NetCDF files (× 6 vars) |
| ---- | -- | -- | -- | ------------ | ----------------------- |
| R1P1 … R10P1 (12 cases) | 5 | 5 | 5 | 15 | 90 |
| R10P7 | 5 | 5 | 1 | 11 | 66 |
| **Total deposit** | | | | | **1146** |

### Why `yz` is the slow plane

The binary files are written in Fortran order on disk: a fixed-`z` (`xy`)
slice or a fixed-`y` (`xz`) slice is read sequentially. A fixed-`x` (`yz`)
slice has to walk through every page of every book to fetch one line — so the
script uses a slab-based `LazyFieldYZ` reader that auto-sizes slabs to fit
~90 % of the SLURM job's memory.

### Filename convention

```
<CASE>_<plane>_<axis><index>_st<sx>x<sy>_<var>.nc
```

For example `R10P7_xy_z3960_st4x4_u.nc` is `u` on the `xy` plane at `z = 3960`,
strided 4×4. The stride defaults to 1×1; pass `--stride sx sy sz` to subsample.

### Run it

```bash
sbatch export_slices.slurm
```

Edit the SLURM script to set the case, variables, planes, indices, and stride.

---

## Stage 3 — 2D slice plotting

`plot_slices.py` reads the NetCDF slices, applies the standard normalisations,
and writes summary + native-resolution PNGs. `plot_slices.ipynb` is the
interactive companion (one cell per step) — convenient for tuning a figure
before kicking off the batch run.

### Normalisations (read from `params.csv`), explained in PHYSICS.pdf

```
uN, vN, wN  =  u, v, w  /  sqrt(Ek)                       velocity components (N stands for normalized)
bN          =  -1000 * Ri * r  /  sqrt(N^2 * Ep)          buoyancy
epslog      =  log10( ee  /  <eps> )                      TKE dissipation
chilog      =  log10( chi /  (<eps> * Gamma1) )           scalar dissipation
```

### Outputs per case

| Type | Layout | Count |
| ---- | ------ | ----- |
| Summary figures (low-res, all 6 variables on one plot) | one per plane, mid-plane index | 3 |
| Native-resolution figures (1 pixel = 1 grid point) | one per (plane, slice index, variable) | up to 6 vars × number of exported slices |

The R10P7 and 12-case totals depend on which slices you ask for. 
By default the script picks the mid-plane slice per plane.

The script caches the slice-discovery scan in
`<CASE>/001_Final/2D_slices/<CASE>_slices_cache.pkl` so successive runs are
fast. Pass `--refresh-cache` to rebuild.

### Run it

```bash
# Single case, default options
python plot_slices.py R1P1

# Or via SLURM for many cases / large grids
sbatch plot_slices.slurm
```

---

## Stage 4 — 3D cube movies (parallel, SLURM)

`make_cube_image.py` renders one stateless cube frame: three orthogonal faces
on a half-open box (Plotly `go.Surface`) plus wireframe edges, with the same
normalisation conventions as stage 3.

`make_cube_movie.py` is the orchestrator. It:

1. Reads grid sizes from `params.csv`.
2. Builds the list of indices along the `--scan` axis (`x`, `y`, or `z`).
3. Spawns one `make_cube_image.py` subprocess per frame via `joblib` (loky backend).
4. Renames the output JPGs into a clean numbered sequence.
5. Stitches them into an MP4 with `ffmpeg` (or `imageio-ffmpeg` if system ffmpeg is missing).

### Defaults worth knowing

```
--scan x          sweep along x (yz face moves left → right)
--scan-stride 1   step between scan-axis indices (smaller = smoother movie)
--ix-frac 0.0     fixed positions of the two non-scanning faces
--iy-frac 0.0
--iz-frac 0.7
--fps 20
--width 2000 px
--njobs 16        match this to --cpus-per-task in SLURM
```

### Run it

```bash
python make_cube_movie.py --case R1P7 --var r --stride 5 \
  --scan x --scan-stride 20 --fps 5 --njobs 16
# or:
sbatch make_cube_movie.slurm
```

Output: `figures/3D/<case>/<var>_scan<axis>_st<stride>/` with JPG frames and
the assembled MP4. Disable BLAS/OMP threading in the SLURM script (set
`OMP_NUM_THREADS=1` etc.) so the 16 workers don't oversubscribe cores.

### One-time install for stage 4

```bash
module load python    # on Andes
pip install --user plotly kaleido imageio-ffmpeg
```

---

## Stage 5 — Web viewer

The browser-based viewer lets people pan and zoom around very large slice PNGs
(via OpenSeadragon Deep Zoom Image pyramids) and play cube-scan MP4s
(via HTML5 `<video>`).

The viewer is accessible at:
https://pub-ae06ec6e266444d2a93dba965f4447b2.r2.dev/site/index.html

Source files live in `viewer/`:

```
viewer/
├── tile_images.py            # PNG → DZI tile pyramids (libvips)
├── gen_slice_manifest.py     # scan tile dir → slice_manifest.json
├── gen_movie_manifest.py     # scan MP4 dir  → movie_manifest.json
├── landing/index.html        # entry page
├── slice_viewer/index.html   # OpenSeadragon viewer
└── movie_viewer/index.html   # HTML5 video viewer
```

See `viewer/README.md` for:

- the full local test recipe (`http://localhost:8000`)
- the Cloudflare R2 deploy recipe
- the bucket structure
- gotchas (range requests, public vs S3 URLs, BASE_URL patching)

The Constellation deposit also includes a self-contained zip with the actual images 
and movies that anyone can unzip and open locally; see the deposit README for that.

---

## Repository layout

```
strata-shear/
├── README.md                  ← this file
├── LICENSE                    ← MIT
├── .gitignore
├── local_config.py.example    ← template (copy to local_config.py)
│
├── params.csv                 ← master parameter table
├── utils.py                   ← shared helpers (~75 KB, commented)
│
├── open_param_nc.ipynb        ← stage 1
├── export_slices.py           ← stage 2
├── export_slices.slurm
├── plot_slices.py             ← stage 3
├── plot_slices.ipynb
├── plot_slices.slurm
├── make_cube_image.py         ← stage 4 (worker)
├── make_cube_movie.py         ← stage 4 (orchestrator)
├── make_cube_movie.slurm
│
└── viewer/                    ← stage 5
    ├── readme.md
    ├── readme_simple.md
    ├── tile_images.py
    ├── gen_slice_manifest.py
    ├── gen_movie_manifest.py
    ├── landing/index.html
    ├── slice_viewer/index.html
    └── movie_viewer/index.html
```

---

## Design choices (and what to remember)

- **Single CSV source of truth** (`params.csv`) — all stages read it, nothing
  hardcodes per-case constants.
- **Separation of slice extraction (stage 2) from plotting (stage 3)** — exporting
  slices once then re-plotting many times is much cheaper than touching the
  raw binaries per figure.
- **Embarrassingly parallel** — stage 2 (one task per plane × index × variable)
  and stage 4 (one task per frame) both saturate a 32-core node.
- **Native-resolution figures** — 1 pixel = 1 grid point, no interpolation,
  for scientific accuracy. The very large PNGs are then tiled in stage 5.
- **Per-machine paths via `local_config.py`** — keeps personal paths out of
  the repo while still letting you run `python plot_slices.py R1P1` with no
  CLI flags.

---

## Citation (to be updaded)

```
@software{lefauve_strata_shear_2026,
  author  = {Lefauve, A. and Couchman, M. M. P. and de Bruyn Kops, S. M.},
  title   = {Strata-shear: post-processing and visualisation pipeline for ...},
  year    = {2026},
  url     = {https://github.com/adrienlefauve/strata-shear},
  license = {MIT}
}
```

---

## Contact
Adrien Lefauve · Imperial College London · `a.lefauve@imperial.ac.uk`
