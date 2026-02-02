#!/usr/bin/env python3
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