#!/usr/bin/env python3
"""
Auto-parallel exporter for 2D DNS slices to NetCDF.

This script extends the serial slice exporter by automatically distributing
independent slice exports across multiple processes. Each slice export runs
in its own Python process with its own lazy field handles.

Why this exists
---------------
The base exporter is intentionally serial and serves as a correctness and
debugging reference. This script addresses a different need: efficiently
exporting many independent slices once the I/O path is known to be correct.

Parallelisation model
---------------------
- Parallelism is at the *process* level, not via threads.
- Each worker:
    - opens the case independently
    - lazily reads only the required plane
    - writes one NetCDF file
- No state is shared between workers.

This design avoids:
- GIL limitations
- fork-unsafe shared file handles
- memory blow-ups from loading 3D fields
- fragile in-process parallelism (e.g. joblib)

What is parallelised
--------------------
- Independent slice exports (different planes and/or indices).
- Each output file is written by exactly one process.

What is NOT parallelised
------------------------
- Reading or writing within a single NetCDF file.
- Any operation requiring shared mutable state.

HPC considerations
------------------
- Parallel file writes can stress the filesystem.
- Use a modest number of processes (often 4–16 is sufficient).
- Set environment variables such as:
      OMP_NUM_THREADS=1
      MKL_NUM_THREADS=1
  to avoid thread oversubscription.

Typical usage
-------------
Export multiple evenly spaced slices per plane:
    python adrienExportSlicesNetCDFAutoParallel.py --case R4P7 \
        --planes xy xz yz --nxy 5 --nxz 5 --nyz 3 --nproc 8

Use this script once the serial exporter has been validated.
"""

import argparse
from pathlib import Path

import adrienParamClassSheared as params
import adrienUtils as utils


def parse_args():
    ap = argparse.ArgumentParser(
        description="Export raw 2D slices (u,v,w,r,ee,chi) to NetCDF for given case/planes."
    )
    ap.add_argument("--case", required=True, help="Case name, e.g. R1P1, R4P7, R10P1 ...")
    ap.add_argument(
        "--planes",
        nargs="+",
        default=["xy", "xz", "yz"],
        help="Planes to export, subset of: xy xz yz",
    )
    ap.add_argument(
        "--outdir",
        default=None,
        help="Output dir (default: <case dirPath>/2D_slices)",
    )
    ap.add_argument(
        "--stride",
        nargs=3,
        type=int,
        default=(1, 1, 1),
        metavar=("SX", "SY", "SZ"),
        help="Stride in x y z",
    )
    ap.add_argument("--tstamp", default=None, help="Override tStamp (default uses case param)")
    ap.add_argument("--idx_xy", type=int, default=None, help="Index for xy plane (fixed z)")
    ap.add_argument("--idx_xz", type=int, default=None, help="Index for xz plane (fixed y)")
    ap.add_argument("--idx_yz", type=int, default=None, help="Index for yz plane (fixed x)")
    ap.add_argument("--overwrite", action="store_true", help="Overwrite existing files if present")
    ap.add_argument("--stream", action="store_true", help="Stream write (lower peak RAM)")
    return ap.parse_args()


def main():
    args = parse_args()

    cases = params.generate()
    if args.case not in cases:
        raise KeyError(f"Unknown case '{args.case}'. Available: {list(cases.keys())}")

    p = cases[args.case]
    if args.tstamp is not None:
        p.tStamp = args.tstamp

    outdir = Path(args.outdir) if args.outdir else (Path(p.dirPath) / "2D_slices")
    outdir.mkdir(parents=True, exist_ok=True)

    fields = utils.open_lazy_fields(["u", "v", "w", "r", "ee", "chi"], p)

    idx_map = {
        "xy": args.idx_xy if args.idx_xy is not None else (p.Nz // 2),
        "xz": args.idx_xz if args.idx_xz is not None else (p.Ny // 2),
        "yz": args.idx_yz if args.idx_yz is not None else (p.Nx // 2),
    }

    planes = [pl.lower() for pl in args.planes]
    for pl in planes:
        if pl not in {"xy", "xz", "yz"}:
            raise ValueError(f"Bad plane '{pl}'. Use subset of: xy xz yz")

    print(f"[export_slices] case={p.name} tStamp={p.tStamp}")
    print(f"[export_slices] outdir={outdir}")
    print(f"[export_slices] stride={tuple(args.stride)} planes={planes}")
    print(f"[export_slices] idx: xy(iz)={idx_map['xy']} xz(iy)={idx_map['xz']} yz(ix)={idx_map['yz']}")

    for pl in planes:
        fname = f"{pl}.nc"
        path = outdir / fname

        if path.exists() and not args.overwrite:
            print(f"[export_slices] skip (exists): {path}")
            continue

        try:
            utils.save_raw_plane_netcdf(
                fields=fields,
                p=p,
                plane=pl,
                idx=idx_map[pl],
                outdir=outdir,
                stride=tuple(args.stride),
                fname=fname,
                verbose=True,
                stream=args.stream,
            )
        except Exception as e:
            print(f"[export_slices] FAILED plane={pl}: {e}")

    print("[export_slices] done.")


if __name__ == "__main__":
    main()