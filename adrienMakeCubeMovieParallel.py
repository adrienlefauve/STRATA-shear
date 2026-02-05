#!/usr/bin/env python3
import argparse
import subprocess
from pathlib import Path
import sys
from joblib import Parallel, delayed


PY = sys.executable   # <<< CRITICAL FIX


def run(cmd):
    print(" ".join(cmd), flush=True)
    subprocess.run(cmd, check=True)


def get_Nx(case: str) -> int:
    cmd = [
        PY, "-c",
        f"import adrienParamClassSheared as p; print(p.generate()['{case}'].Nx)"
    ]
    return int(subprocess.check_output(cmd).decode().strip())


def render_one_frame(
    case, var, stride, ix, top_frac,
    width, scale, cbar,
    outdir, frames_dir, frame_no
):
    cmd = [
        PY, "adrienPlotCube.py",
        "--case", case,
        "--var", var,
        "--stride", str(stride),
        "--ix", str(ix),
        "--top-frac", str(top_frac),
        "--width", str(width),
        "--scale", str(scale),
    ]
    if cbar:
        cmd.append("--cbar")

    run(cmd)

    produced = Path(outdir) / case / f"{case}_{var}_ix{ix:06d}.png"
    if not produced.exists():
        raise FileNotFoundError(f"Expected output not found: {produced}")

    target = Path(frames_dir) / f"{case}_{var}_{frame_no:06d}.png"
    target.unlink(missing_ok=True)
    produced.replace(target)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--case", required=True)
    ap.add_argument("--var", default="r")
    ap.add_argument("--stride", type=int, default=1)
    ap.add_argument("--ixstride", type=int, default=1)
    ap.add_argument("--fps", type=int, default=20)
    ap.add_argument("--width", type=int, default=2000)
    ap.add_argument("--scale", type=float, default=1.0)
    ap.add_argument("--top-frac", type=float, default=0.8)
    ap.add_argument("--cbar", action="store_true")
    ap.add_argument("--outdir", default="figures/3D")
    ap.add_argument("--njobs", type=int, default=16)
    ap.add_argument("--crf", type=int, default=18)
    ap.add_argument("--preset", default="medium")
    args = ap.parse_args()

    print(f"\nUsing Python interpreter:\n  {PY}\n", flush=True)

    outdir = Path(args.outdir)
    frames_dir = outdir / args.case / f"{args.var}_frames"
    frames_dir.mkdir(parents=True, exist_ok=True)

    Nx = get_Nx(args.case)
    ix_vals = list(range(0, Nx, args.ixstride))
    tasks = [(ix, i + 1) for i, ix in enumerate(ix_vals)]

    Parallel(
        n_jobs=args.njobs,
        backend="loky",
        verbose=10,
    )(
        delayed(render_one_frame)(
            args.case, args.var, args.stride, ix, args.top_frac,
            args.width, args.scale, args.cbar,
            str(outdir), str(frames_dir), frame_no
        )
        for (ix, frame_no) in tasks
    )

    movie = outdir / args.case / f"{args.case}_{args.var}.mp4"
    run([
        "ffmpeg", "-y",
        "-framerate", str(args.fps),
        "-i", str(frames_dir / f"{args.case}_{args.var}_%06d.png"),
        "-c:v", "libx264",
        "-pix_fmt", "yuv420p",
        "-crf", str(args.crf),
        "-preset", args.preset,
        str(movie),
    ])

    print(f"\nMovie written to:\n  {movie}\n")


if __name__ == "__main__":
    main()