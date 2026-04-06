#!/usr/bin/env python3
# A. Lefauve, 2026
"""
Parallel cube-movie maker.

  python make_cube_movie.py \\
      --case R1P7 --var r --stride 5 \\
      --scan x --scan-stride 20 \\
      --fps 5 --width 1000 --njobs 16

WORKFLOW
--------
  1. Read grid sizes from params.csv for the requested case.
  2. Build a list of ORIGINAL indices along the scan axis:
       0, scan-stride, 2×scan-stride, …
  3. Render every frame in parallel (joblib / loky backend).
     Each worker spawns:  python make_cube_image.py --scan <axis> --idx <i> …
  4. Rename output PNGs into sequentially numbered frames.
  5. (Optional) Stitch frames into an MP4 with ffmpeg.

SCAN AXIS
---------
  --scan x  : sweep along x (yz face moves left→right).   The default.
  --scan y  : sweep along y (xz face moves front→back).
  --scan z  : sweep along z (xy face moves bottom→top).

  The two non-scanning faces are fixed at fractional positions:
    --ix-frac  (default 0.0 = left wall)
    --iy-frac  (default 0.0 = front wall)
    --iz-frac  (default 0.7 = near the top)

PARALLELISM
-----------
  Embarrassingly parallel over frames (one frame per scan index).
  Each worker is an independent stateless subprocess.
  Set --njobs to match --cpus-per-task in SLURM.
  Disable BLAS/OMP threading (done automatically in make_cube_movie.slurm)
  to avoid oversubscription.

OUTPUT
------
  <outdir>/<case>/<run_tag>/<case>_<var>_000001.jpg  …
  <outdir>/<case>/<run_tag>/<run_tag>.mp4

  where <run_tag> = <var>_scan<scan>_st<stride>

  Pass --no-movie to skip the ffmpeg step (e.g. to render frames first,
  then tweak fps / crf and run ffmpeg manually).

TUNING
------
  --stride S      : downsample the 3D volume (smaller S = sharper but slower)
  --scan-stride N : step between scan-axis indices (smaller = smoother movie)
  --fps F         : frames per second in the output movie
  --crf C         : ffmpeg quality (lower = better, 18 is visually lossless)
  --width W       : image width in pixels (height = 0.7 × width)

  Example for a quick preview:
    --stride 30 --scan-stride 100 --width 800 --fps 10
  Example for publication:
    --stride 5  --scan-stride 10  --width 2000 --fps 20 --crf 15

  Sweep along z (top face moves bottom→top):
    python make_cube_movie.py \\
        --case R1P7 --var r --stride 5 \\
        --scan z --scan-stride 5 \\
        --ix-frac 0.0 --iy-frac 0.0 \\
        --fps 10 --njobs 16
"""

import argparse
import subprocess
import sys
from pathlib import Path

import pandas as pd
from joblib import Parallel, delayed

# ---------------------------------------------------------------------------
# Read grid sizes from params.csv (no paramClass dependency)
# ---------------------------------------------------------------------------

CSV_PATH = Path(__file__).parent / "params.csv"


def get_grid_sizes(case: str) -> dict:
    """Return {"x": Nx, "y": Ny, "z": Nz} for the given case."""
    df = pd.read_csv(CSV_PATH, dtype={"tStamp": str})
    by_case = {str(row["name"]).strip(): row for _, row in df.iterrows()}
    if case not in by_case:
        raise KeyError(f"Unknown case '{case}'. Available: {list(by_case.keys())}")
    nx = int(float(by_case[case]["Nx"]))
    return {"x": nx, "y": nx // 2, "z": nx // 4}


# ---------------------------------------------------------------------------

PY = sys.executable


def run(cmd):
    print(" ".join(cmd), flush=True)
    subprocess.run(cmd, check=True)


def render_one_frame(
    case, var, stride, scan, idx,
    ix_frac, iy_frac, iz_frac,
    width, scale, no_cbar, tstamp,
    outdir, run_tag, frames_dir, frame_no,
):
    cmd = [
        PY, str(Path(__file__).parent / "make_cube_image.py"),
        "--case", case,
        "--var", var,
        "--stride", str(stride),
        "--scan", scan,
        "--idx", str(idx),
        "--ix-frac", str(ix_frac),
        "--iy-frac", str(iy_frac),
        "--iz-frac", str(iz_frac),
        "--width", str(width),
        "--scale", str(scale),
        "--outdir", outdir,
        "--run-tag", run_tag,
    ]
    if no_cbar:
        cmd.append("--no-cbar")
    if tstamp is not None:
        cmd += ["--tstamp", str(tstamp)]

    run(cmd)

    # make_cube_image.py writes:  <outdir>/<case>/<run_tag>/<case>_<var>_i<scan><idx>.jpg
    produced = Path(outdir) / case / run_tag / f"{case}_{var}_i{scan}{idx:06d}.jpg"
    if not produced.exists():
        raise FileNotFoundError(f"Expected output not found: {produced}")

    target = Path(frames_dir) / f"{case}_{var}_{frame_no:06d}.jpg"
    if target.exists():
        target.unlink()
    produced.replace(target)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser(
        description="Render cube frames in parallel and assemble an MP4."
    )
    ap.add_argument("--case",      required=True)
    ap.add_argument("--var",       default="r")
    ap.add_argument("--stride",    type=int, default=1,
                    help="Downsample factor for the 3D volume")
    ap.add_argument("--scan",      default="x", choices=["x", "y", "z"],
                    help="Axis to sweep along (default: x)")
    ap.add_argument("--scan-stride", type=int, default=1,
                    help="Step between indices along the scan axis")
    ap.add_argument("--ix-frac",   type=float, default=0.0,
                    help="Fraction of Nx for the fixed x-face")
    ap.add_argument("--iy-frac",   type=float, default=0.0,
                    help="Fraction of Ny for the fixed y-face")
    ap.add_argument("--iz-frac",   type=float, default=0.7,
                    help="Fraction of Nz for the fixed z-face")
    ap.add_argument("--fps",       type=int, default=20)
    ap.add_argument("--width",     type=int, default=2000)
    ap.add_argument("--scale",     type=float, default=1.0)
    ap.add_argument("--no-cbar",   action="store_true",
                    help="Hide colorbar (shown by default)")
    ap.add_argument("--outdir",    default="figures/3D")
    ap.add_argument("--njobs",     type=int, default=16)
    ap.add_argument("--crf",       type=int, default=18,
                    help="ffmpeg CRF (lower = better quality)")
    ap.add_argument("--preset",    default="medium",
                    help="ffmpeg x264 preset")
    ap.add_argument("--no-movie",  action="store_true",
                    help="Only render frames, skip ffmpeg")
    ap.add_argument("--tstamp",    default=None)
    args = ap.parse_args()

    print(f"\nUsing Python interpreter:\n  {PY}\n", flush=True)

    outdir     = Path(args.outdir)
    run_tag    = f"{args.var}_scan{args.scan}_st{args.stride}"
    frames_dir = outdir / args.case / run_tag
    frames_dir.mkdir(parents=True, exist_ok=True)

    grid = get_grid_sizes(args.case)
    N_scan = grid[args.scan]
    idx_vals = list(range(0, N_scan, args.scan_stride))
    tasks = [(idx, i + 1) for i, idx in enumerate(idx_vals)]
    print(f"case={args.case}  scan={args.scan}  N{args.scan}={N_scan}  "
          f"scan-stride={args.scan_stride}  → {len(tasks)} frames  "
          f"njobs={args.njobs}\n", flush=True)

    Parallel(
        n_jobs=args.njobs,
        backend="loky",
        verbose=10,
    )(
        delayed(render_one_frame)(
            args.case, args.var, args.stride, args.scan, idx,
            args.ix_frac, args.iy_frac, args.iz_frac,
            args.width, args.scale, args.no_cbar, args.tstamp,
            str(outdir), run_tag, str(frames_dir), frame_no,
        )
        for idx, frame_no in tasks
    )

    if args.no_movie:
        print(f"\nFrames written to:\n  {frames_dir}\n")
        return

    movie = frames_dir / f"{run_tag}.mp4"
    run([
        "ffmpeg", "-y",
        "-framerate", str(args.fps),
        "-i", str(frames_dir / f"{args.case}_{args.var}_%06d.jpg"),
        "-c:v", "libx264",
        "-pix_fmt", "yuv420p",
        "-crf", str(args.crf),
        "-preset", args.preset,
        str(movie),
    ])
    print(f"\nMovie written to:\n  {movie}\n")


if __name__ == "__main__":
    main()
