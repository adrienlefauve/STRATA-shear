#!/usr/bin/env python3
"""
adrienMakeCubeMovie.py

Workflow
--------
1) Loops over x-indices (ix) in the ORIGINAL volume (0..Nx-1) with step --ixstride.
2) For each ix, calls adrienPlotCube.py to render one PNG:
      figures/3D/<case>/<case>_<var>_ixXXXXXX.png
3) Renames/moves each PNG into a sequential frame directory:
      figures/3D/<case>/<var>_frames/<case>_<var>_000001.png, ...
4) Optionally runs ffmpeg to make an mp4.

Notes
-----
- Requires adrienPlotCube.py to be functional in your environment.
- ffmpeg is optional: pass --no-movie if you only want frames, or pass --ffmpeg /path/to/ffmpeg.
"""

# EXAMPLE CALL
# python adrienMakeCubeMovie.py \
#   --case R1P1 \
#   --var r \
#   --stride 1 \
#   --ixstride 10 \
#   --fps 10 \
#   --cbar \
#   --width 1500

import argparse
import subprocess
from pathlib import Path


def run(cmd):
    print(" ".join(cmd), flush=True)
    subprocess.run(cmd, check=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--case", required=True)
    ap.add_argument("--var", default="r")
    ap.add_argument("--stride", type=int, default=1, help="downsampling stride passed to plot script")
    ap.add_argument("--ixstride", type=int, default=1, help="step in ORIGINAL ix")
    ap.add_argument("--fps", type=int, default=20)
    ap.add_argument("--width", type=int, default=2000)
    ap.add_argument("--scale", type=float, default=1.0)
    ap.add_argument("--top-frac", type=float, default=0.8)
    ap.add_argument("--cbar", action="store_true")
    ap.add_argument("--outdir", default="figures/3D")

    args = ap.parse_args()

    frames_dir = Path(args.outdir) / args.case / f"{args.var}_frames"
    frames_dir.mkdir(parents=True, exist_ok=True)

    # Query Nx from param file via a tiny python one-liner
    get_Nx = [
        "python", "-c",
        (
            "import adrienParamClassSheared as p;"
            f"print(p.generate()['{args.case}'].Nx)"
        ),
    ]
    Nx = int(subprocess.check_output(get_Nx).decode().strip())

    frame = 0
    for ix in range(0, Nx, args.ixstride):
        frame += 1

        outpng = frames_dir / f"{args.case}_{args.var}_{frame:06d}.png"

        cmd = [
            "python", "adrienPlotCube.py",
            "--case", args.case,
            "--var", args.var,
            "--stride", str(args.stride),
            "--ix", str(ix),
            "--top-frac", str(args.top_frac),
            "--width", str(args.width),
            "--scale", str(args.scale),
        ]
        if args.cbar:
            cmd.append("--cbar")

        run(cmd)

        produced = Path(args.outdir) / args.case / f"{args.case}_{args.var}_ix{ix:06d}.png"
        produced.replace(outpng)

    # Make movie
    movie = Path(args.outdir) / args.case / f"{args.case}_{args.var}.mp4"

    run([
        "ffmpeg", "-y",
        "-framerate", str(args.fps),
        "-i", str(frames_dir / f"{args.case}_{args.var}_%06d.png"),
        "-c:v", "libx264",
        "-pix_fmt", "yuv420p",
        "-crf", "18",
        str(movie),
    ])

    print(f"\nMovie written to:\n  {movie}\n")


if __name__ == "__main__":
    main()