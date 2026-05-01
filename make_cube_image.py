#!/usr/bin/env python3
# A. Lefauve, 2026
"""
Render a single 3D cube snapshot from DNS binary data.

  python plot_cube.py --case R1P7 --var r --stride 5 --scan x --idx 400 --cbar

  # Sweep along z instead, with fixed x/y faces:
  python plot_cube.py --case R1P7 --var r --stride 5 \\
      --scan z --idx 100 --ix-frac 0.0 --iy-frac 0.0

GEOMETRY
--------
  Three orthogonal surfaces on a half-open box:
    • one face perpendicular to x  (yz plane at x = ix)
    • one face perpendicular to y  (xz plane at y = iy)
    • one face perpendicular to z  (xy plane at z = iz)
  Plus 12 black wireframe edges.  Fixed aspect ratio 1 : 0.5 : 0.25
  matching the DNS domain Lx : Ly : Lz.

SCAN AXIS
---------
  --scan x|y|z : which axis the movie sweeps along.
  --idx N      : index in the ORIGINAL grid along the scan axis for this frame.

  The other two faces are fixed at:
    --iy-frac / --iz-frac  (when scanning x — default)
    --ix-frac / --iz-frac  (when scanning y)
    --ix-frac / --iy-frac  (when scanning z)

  Each *-frac is a fraction ∈ [0, 1] of the axis length, default:
    ix-frac = 0.0  (left wall),  iy-frac = 0.0  (front wall),
    iz-frac = 0.7  (top slice near the top).

DOWNSAMPLING
------------
  --stride S : uniform downsampling in x, y, z by factor S.
  The cube is loaded via memmap and sliced as data[::S, ::S, ::S],
  so peak RAM ≈ (Nx/S)×(Ny/S)×(Nz/S)×4 bytes.
  For R10P7 at stride 30:  31680/30 × 15840/30 × 7920/30 ≈ 155 M floats ≈ 0.6 GB.

COLOUR LIMITS
-------------
  Hard-coded per variable in VARCFG so that all frames in a movie are
  visually consistent.  Edit VARCFG to change colorscale or clim.

OUTPUT
------
  <outdir>/<case>/<run_tag>/<case>_<var>_i<scan><idx:06d>.jpg

  where <run_tag> = <var>_scan<scan>_st<stride>  (set via --run-tag
  or auto-generated).  One call → one PNG.  Stateless by design so it
  can be called many times in parallel by make_cube_movie.py.

PARAMETERS
----------
  Read from params.csv (same format as export_slices.py).
  --tstamp overrides the snapshot timestamp if needed.
"""

import argparse
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from types import SimpleNamespace

# ---------------------------------------------------------------------------
# Parameter helpers (same pattern as export_slices.py)
# ---------------------------------------------------------------------------

CSV_PATH     = Path(__file__).parent / "params.csv"

# Override via local_config.py — see local_config.py.example
try:
    from local_config import PROJECT_ROOT
except ImportError:
    PROJECT_ROOT = Path(__file__).resolve().parent / "data"   # placeholder; override in local_config.py
PARAMS_DF    = pd.read_csv(CSV_PATH, dtype={"tStamp": str})
PARAMS_BY_CASE = {str(row["name"]).strip(): row for _, row in PARAMS_DF.iterrows()}


def build_case(case_name: str, tstamp_override=None):
    if case_name not in PARAMS_BY_CASE:
        raise KeyError(f"Unknown case '{case_name}'. Available: {list(PARAMS_BY_CASE.keys())}")
    row = PARAMS_BY_CASE[case_name]
    nx  = int(float(row["Nx"]))
    Lx  = float(row["Lx"])
    p   = SimpleNamespace()
    p.name    = str(row["name"]).strip()
    p.tStamp  = (f"{float(tstamp_override):.6f}" if tstamp_override is not None
                 else str(row["tStamp"]).strip())
    p.Nx = nx;  p.Ny = nx // 2;  p.Nz = nx // 4
    p.Lx = Lx;  p.Ly = Lx / 2;  p.Lz = Lx / 4
    p.dirPath = str(PROJECT_ROOT / p.name / "001_Final") + "/"
    # Physics parameters for normalisation (same as plot_slices.py)
    p.Ri      = float(row["Ri"])
    p.Ek      = float(row["Ek"])
    p.Ep      = float(row["Ep"])
    p.eps     = float(row["ek"])       # volume-averaged epsilon
    p.chi     = float(row["ep"])       # volume-averaged chi
    p.Gamma1  = float(row["Gamma1"])
    p.N2      = p.Ri                   # N^2 = Ri (dimensionless)
    return p


# ---------------------------------------------------------------------------
# Per-variable visual config
# ---------------------------------------------------------------------------

VARCFG = {
    # var : (plotly_colorscale, cmin, cmax, colorbar_title, tickvals)
    "u":   ("RdBu",    -5,     5,     "u' / E<sub>k</sub><sup>1/2</sup>",      [-5, 0, 5]),
    "v":   ("RdBu",    -5,     5,     "v' / E<sub>k</sub><sup>1/2</sup>",      [-5, 0, 5]),
    "w":   ("RdBu",    -5,     5,     "w' / E<sub>k</sub><sup>1/2</sup>",      [-5, 0, 5]),
    "r":   ("Viridis", -5,     5,     "b' / (N E<sub>p</sub><sup>1/2</sup>)",  [-5, 0, 5]),
    "b":   ("Viridis", -5,     5,     "b' / (N E<sub>p</sub><sup>1/2</sup>)",  [-5, 0, 5]),
    "ee":  ("Magma",   -2,     2,     "log<sub>10</sub>(ε / ⟨ε⟩)",             [-2, 0, 2]),
    "chi": ("Hot",     -2,     3,     "log<sub>10</sub>(χ / ⟨χ⟩)",             [-2, 0, 3]),
}


# ---------------------------------------------------------------------------
# I/O
# ---------------------------------------------------------------------------

def load_binary(var_name, p, dtype="single", order="F", chop_x_pad=2):
    file_path = Path(p.dirPath) / f"{var_name}_{p.tStamp}"
    X = np.memmap(
        str(file_path),
        dtype=dtype,
        mode="r",
        shape=(p.Nx + chop_x_pad, p.Ny, p.Nz),
        order=order,
    )
    return X[:-chop_x_pad, :, :]


# ---------------------------------------------------------------------------
# Plotly rendering
# ---------------------------------------------------------------------------

def plot_one_frame(
    cube, x, y, z,
    ix, iy, iz,
    scan,
    cmin, cmax, colorscale, ctitle,
    tickvals=None,
    add_colorbar=True,
    width=2500, height=1406,
):
    """Render three orthogonal faces of a downsampled cube.

    Parameters
    ----------
    cube : (Nx_ds, Ny_ds, Nz_ds) array
    x, y, z : 1-D coordinate arrays (downsampled)
    ix, iy, iz : int indices into the downsampled cube for each face
    scan : "x", "y", or "z" — the axis that sweeps (determines which
           face extends only from the scan index onward)
    """
    X, Y, Z = np.meshgrid(x, y, z, indexing="ij")

    fig = go.Figure()

    cbar_kw = dict(
        colorbar=dict(title=dict(text=ctitle, side="right"),
                      len=0.55, thickness=20, x=1.02,
                      tickvals=tickvals,
                      tickfont=dict(size=13)),
    ) if add_colorbar else {}

    # --- xy face (z = iz) — top ---
    if scan == "x":
        fig.add_trace(go.Surface(
            x=X[ix:, :, iz], y=Y[ix:, :, iz], z=Z[ix:, :, iz],
            surfacecolor=cube[ix:, :, iz],
            colorscale=colorscale, cmin=cmin, cmax=cmax,
            showscale=add_colorbar, **cbar_kw,
        ))
    elif scan == "y":
        fig.add_trace(go.Surface(
            x=X[:, iy:, iz], y=Y[:, iy:, iz], z=Z[:, iy:, iz],
            surfacecolor=cube[:, iy:, iz],
            colorscale=colorscale, cmin=cmin, cmax=cmax,
            showscale=add_colorbar, **cbar_kw,
        ))
    else:  # scan == "z"
        fig.add_trace(go.Surface(
            x=X[:, :, iz], y=Y[:, :, iz], z=Z[:, :, iz],
            surfacecolor=cube[:, :, iz],
            colorscale=colorscale, cmin=cmin, cmax=cmax,
            showscale=add_colorbar, **cbar_kw,
        ))

    # --- xz face (y = iy) — front ---
    if scan == "x":
        fig.add_trace(go.Surface(
            x=X[ix:, iy, :iz+1], y=Y[ix:, iy, :iz+1], z=Z[ix:, iy, :iz+1],
            surfacecolor=cube[ix:, iy, :iz+1],
            colorscale=colorscale, cmin=cmin, cmax=cmax,
            showscale=False,
        ))
    elif scan == "y":
        fig.add_trace(go.Surface(
            x=X[:, iy, :iz+1], y=Y[:, iy, :iz+1], z=Z[:, iy, :iz+1],
            surfacecolor=cube[:, iy, :iz+1],
            colorscale=colorscale, cmin=cmin, cmax=cmax,
            showscale=False,
        ))
    else:  # scan == "z"
        fig.add_trace(go.Surface(
            x=X[:, iy, :iz+1], y=Y[:, iy, :iz+1], z=Z[:, iy, :iz+1],
            surfacecolor=cube[:, iy, :iz+1],
            colorscale=colorscale, cmin=cmin, cmax=cmax,
            showscale=False,
        ))

    # --- yz face (x = ix) — left ---
    if scan == "x":
        fig.add_trace(go.Surface(
            x=X[ix, :, :iz+1], y=Y[ix, :, :iz+1], z=Z[ix, :, :iz+1],
            surfacecolor=cube[ix, :, :iz+1],
            colorscale=colorscale, cmin=cmin, cmax=cmax,
            showscale=False,
        ))
    elif scan == "y":
        fig.add_trace(go.Surface(
            x=X[ix, iy:, :iz+1], y=Y[ix, iy:, :iz+1], z=Z[ix, iy:, :iz+1],
            surfacecolor=cube[ix, iy:, :iz+1],
            colorscale=colorscale, cmin=cmin, cmax=cmax,
            showscale=False,
        ))
    else:  # scan == "z"
        fig.add_trace(go.Surface(
            x=X[ix, :, :iz+1], y=Y[ix, :, :iz+1], z=Z[ix, :, :iz+1],
            surfacecolor=cube[ix, :, :iz+1],
            colorscale=colorscale, cmin=cmin, cmax=cmax,
            showscale=False,
        ))

    # --- Box edges ---
    x0, x1 = x[0], x[-1]
    y0, y1 = y[0], y[-1]
    z0, z1 = z[0], z[-1]
    lines = [
        ([x0,x1],[y0,y0],[z0,z0]), ([x1,x1],[y0,y0],[z0,z1]),
        ([x1,x0],[y0,y0],[z1,z1]), ([x0,x0],[y0,y0],[z1,z0]),
        ([x0,x1],[y1,y1],[z0,z0]), ([x1,x1],[y1,y1],[z0,z1]),
        ([x1,x0],[y1,y1],[z1,z1]), ([x0,x0],[y1,y1],[z1,z0]),
        ([x0,x0],[y0,y1],[z0,z0]), ([x1,x1],[y0,y1],[z0,z0]),
        ([x1,x1],[y0,y1],[z1,z1]), ([x0,x0],[y0,y1],[z1,z1]),
    ]
    for xi, yi, zi in lines:
        fig.add_trace(go.Scatter3d(
            x=xi, y=yi, z=zi,
            mode="lines", line=dict(color="black", width=6),
            showlegend=False,
        ))

    fig.update_layout(
        autosize=False, width=width, height=height,
        margin=dict(l=0, r=0, b=0, t=0),
        scene=dict(
            domain=dict(x=[0, 1], y=[0, 1]),
            aspectmode="manual",
            aspectratio=dict(x=1, y=1/2, z=1/4),
            xaxis=dict(visible=False, showspikes=False, range=[x0, x1]),
            yaxis=dict(visible=False, showspikes=False, range=[y0, y1]),
            zaxis=dict(visible=False, showspikes=False, range=[z0, z1]),
            camera=dict(
                eye=dict(x=-0.7, y=-0.7, z=0.5),
                center=dict(x=-0.08, y=0, z=-0.12),
            ),
        ),
    )
    return fig


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser(
        description="Render one 3D cube frame to PNG."
    )
    ap.add_argument("--case",      required=True)
    ap.add_argument("--var",       default="r")
    ap.add_argument("--stride",    type=int, default=30,
                    help="Downsample stride in x,y,z")
    ap.add_argument("--scan",      default="x", choices=["x", "y", "z"],
                    help="Axis to sweep along (default: x)")
    ap.add_argument("--idx",       type=int, required=True,
                    help="Index along the scan axis in the ORIGINAL grid")
    ap.add_argument("--ix-frac",   type=float, default=0.0,
                    help="Fraction of Nx for the fixed x-face (when scanning y or z)")
    ap.add_argument("--iy-frac",   type=float, default=0.0,
                    help="Fraction of Ny for the fixed y-face (when scanning x or z)")
    ap.add_argument("--iz-frac",   type=float, default=0.7,
                    help="Fraction of Nz for the fixed z-face (when scanning x or y)")
    ap.add_argument("--outdir",    default="figures/3D/")
    ap.add_argument("--run-tag",   default=None,
                    help="Subdirectory name under <outdir>/<case>/. "
                         "Auto-generated if not set: <case>_<var>_st<stride>_scan<scan>")
    ap.add_argument("--width",     type=int, default=2000)
    ap.add_argument("--scale",     type=float, default=1.0)
    ap.add_argument("--no-cbar",   action="store_true",
                    help="Hide colorbar (shown by default)")
    ap.add_argument("--tstamp",    default=None)
    args = ap.parse_args()

    p = build_case(args.case, tstamp_override=args.tstamp)

    if args.var not in VARCFG:
        raise ValueError(f"--var {args.var} not in VARCFG. Add it there.")
    colorscale, cmin, cmax, ctitle, tickvals = VARCFG[args.var]

    # Validate scan index
    scan_N = {"x": p.Nx, "y": p.Ny, "z": p.Nz}[args.scan]
    if args.idx < 0 or args.idx >= scan_N:
        raise ValueError(f"--idx must be in [0, {scan_N - 1}] for scan={args.scan}. Got {args.idx}")

    data = load_binary(args.var, p)
    S = args.stride
    raw = data[::S, ::S, ::S].copy()  # materialise from memmap

    # Per-variable normalisation (matches plot_slices.py exactly)
    if args.var in ("u", "v", "w"):
        cube = raw / np.sqrt(p.Ek)
    elif args.var == "r":
        # buoyancy: b'/(N sqrt(Ep));  zAccel = Ri/|dGrad| = 1000*Ri
        cube = -1000.0 * p.Ri * raw / np.sqrt(p.N2 * p.Ep)
    elif args.var in ("ee", "chi"):
        if args.var == "ee":
            avg = float(p.eps)
        else:
            avg = float(p.eps * p.Gamma1)
        tiny = 1e-30
        with np.errstate(divide="ignore", invalid="ignore"):
            cube = np.log10(np.maximum(raw, tiny) / avg)
    else:
        cube = raw  # fallback: no normalisation

    Nx_ds, Ny_ds, Nz_ds = cube.shape

    # Map original index → downsampled index for the scan axis
    scan_idx_ds = max(0, min(args.idx // args.stride,
                             {"x": Nx_ds, "y": Ny_ds, "z": Nz_ds}[args.scan] - 1))

    # Fixed faces: fraction → downsampled index
    def frac_to_idx(frac, N_ds):
        return max(0, min(int(round(frac * (N_ds - 1))), N_ds - 1))

    if args.scan == "x":
        ix = scan_idx_ds
        iy = frac_to_idx(args.iy_frac, Ny_ds)
        iz = frac_to_idx(args.iz_frac, Nz_ds)
    elif args.scan == "y":
        ix = frac_to_idx(args.ix_frac, Nx_ds)
        iy = scan_idx_ds
        iz = frac_to_idx(args.iz_frac, Nz_ds)
    else:  # z
        ix = frac_to_idx(args.ix_frac, Nx_ds)
        iy = frac_to_idx(args.iy_frac, Ny_ds)
        iz = scan_idx_ds

    x = np.linspace(0, 1.0,  Nx_ds)
    y = np.linspace(0, 0.5,  Ny_ds)
    z = np.linspace(0, 0.25, Nz_ds)

    height = int(args.width * 0.7)

    fig = plot_one_frame(
        cube, x, y, z,
        ix=ix, iy=iy, iz=iz,
        scan=args.scan,
        cmin=cmin, cmax=cmax,
        colorscale=colorscale, ctitle=ctitle,
        tickvals=tickvals,
        add_colorbar=not args.no_cbar,
        width=args.width, height=height,
    )

    run_tag = args.run_tag or f"{args.var}_scan{args.scan}_st{args.stride}"
    outdir = Path(args.outdir) / args.case / run_tag
    outdir.mkdir(parents=True, exist_ok=True)

    tag = f"i{args.scan}{args.idx:06d}"
    outpath = outdir / f"{p.name}_{args.var}_{tag}.jpg"
    if outpath.exists():
        outpath.unlink()

    fig.write_image(str(outpath), width=args.width, height=height, scale=args.scale)
    print(f"wrote {outpath}", flush=True)


if __name__ == "__main__":
    main()
