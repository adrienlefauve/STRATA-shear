#!/usr/bin/env python3
# A. Lefauve, 2026
"""
Export yz slices from DNS binary data for heavy (large-Nx) cases.

KEY DIFFERENCE from export_netcdf_slices_from_binary_3D.py
  For yz planes, one worker = one variable.  All requested x-indices for
  that variable are extracted in a SINGLE sequential pass through the file
  (LazyField.slice2d_multi_yz).  The file is never read more than once,
  regardless of how many yz slices are requested.

Why this matters on Lustre
  The binary files are Fortran-order (x fastest).  A yz slice at a fixed
  x-index requires accessing every (Nx+2)*Ny-th byte, i.e. one seek per
  element (~128 KB gaps for Nx=32000).  The slab-reader converts this to
  large sequential reads by loading full (Nx+2)*Ny*chunk_nz blocks, then
  extracting the desired x rows in RAM.

Parallelism model
  nproc workers, one per variable.  All variables are processed
  concurrently; since each worker reads a different file there is no
  filesystem contention between workers.

  Peak RAM ≈ nproc × (yz_chunk_mem_gb + n_slices * Ny * Nz * 4 bytes)
           = nproc × (yz_chunk_mem_gb + small)

  For R8P7 on a 128 GB node:
    nproc=6, yz_chunk_mem_gb=18 → 6 × (18 + 1.3) ≈ 116 GB   ✓
  For R10P7 on a 128 GB node:
    nproc=4, yz_chunk_mem_gb=28 → 4 × (28 + 1.5) ≈ 118 GB   ✓

Typical call
  python export_yz_heavy.py \\
    --case R8P7 \\
    --nyz 5 \\
    --vars u v w r ee chi \\
    --nproc 6 \\
    --yz-chunk-mem-gb 18 \\
    --stride 1 1 1 \\
    --overwrite
"""

import argparse
from pathlib import Path
import multiprocessing as mp
import pandas as pd
from types import SimpleNamespace

import numpy as np

import utils_yz

print("[export_yz_heavy] starting", flush=True)

CSV_PATH    = Path("params.csv")
PROJECT_ROOT = Path("/lustre/orion/cfd135/proj-shared/Hsst")
PARAMS_DF   = pd.read_csv(CSV_PATH, dtype={"tStamp": str})
PARAMS_BY_CASE = {str(row["name"]).strip(): row for _, row in PARAMS_DF.iterrows()}


# ---------------------------------------------------------------------------
# Case builder (mirrors export_netcdf_slices_from_binary_3D.py exactly)
# ---------------------------------------------------------------------------

def build_case_from_csv(case_name: str, tstamp_override=None):
    if case_name not in PARAMS_BY_CASE:
        raise KeyError(f"Unknown case '{case_name}'. Available: {list(PARAMS_BY_CASE.keys())}")

    row   = PARAMS_BY_CASE[case_name]
    nx    = int(float(row["Nx"]))
    Lx    = float(row["Lx"])

    p      = SimpleNamespace()
    p.name = str(row["name"]).strip()

    if tstamp_override is not None:
        p.tStamp = f"{float(tstamp_override):.6f}"
    else:
        p.tStamp = str(row["tStamp"]).strip()

    p.Nx      = nx
    p.Ny      = nx // 2
    p.Nz      = nx // 4
    p.Lx      = Lx
    p.Ly      = Lx / 2
    p.Lz      = Lx / 4
    p.dirPath = str(PROJECT_ROOT / p.name / "001_Final") + "/"

    return p


# ---------------------------------------------------------------------------
# NetCDF writer for a pre-loaded yz slice
# ---------------------------------------------------------------------------

def _write_yz_netcdf(arr2d: np.ndarray, p, x_idx: int, stride,
                     outdir: Path, fname: str, overwrite: bool) -> str:
    varname = Path(fname).stem.split("_")[-1]
    return utils_yz.write_yz_netcdf(
        arr2d=arr2d,
        varname=varname,
        p=p,
        x_idx=x_idx,
        stride=stride,
        outdir=outdir,
        fname=fname,
        overwrite=overwrite,
    )


# ---------------------------------------------------------------------------
# Worker globals (one copy per worker process)
# ---------------------------------------------------------------------------

_G: dict = {}


def _worker_init(case_name: str, tstamp, outdir: str, stride,
                 overwrite: bool, yz_chunk_mem_gb: float, x_idxs: list):
    p = build_case_from_csv(case_name, tstamp_override=tstamp)
    outdir_p = Path(outdir)
    outdir_p.mkdir(parents=True, exist_ok=True)

    _G["p"]                = p
    _G["outdir"]           = outdir_p
    _G["stride"]           = tuple(stride)
    _G["overwrite"]        = bool(overwrite)
    _G["yz_chunk_mem_gb"]  = float(yz_chunk_mem_gb)
    _G["x_idxs"]           = list(x_idxs)


def _worker_run(var: str):
    """
    Worker entry point.  task = variable name (str).
    Reads the file ONCE, extracts all x_idxs, writes N netcdf files.
    """
    try:
        p        = _G["p"]
        outdir   = _G["outdir"]
        stride   = _G["stride"]
        overwrite = _G["overwrite"]
        chunk_gb = _G["yz_chunk_mem_gb"]
        x_idxs   = _G["x_idxs"]
        sx, sy, sz = stride

        # Filename stride tag (only y,z relevant for yz plane)
        st_tag = f"{sy}x{sz}"

        # Check which indices still need to be computed (skip-logic)
        pending_idxs = []
        for x_idx in x_idxs:
            fname = f"{p.name}_yz_x{x_idx}_st{st_tag}_{var}.nc"
            if not (outdir / fname).exists() or overwrite:
                pending_idxs.append(x_idx)
            else:
                print(f"[skip] {fname} exists", flush=True)

        if not pending_idxs:
            return [f"[skip-all] var={var} all {len(x_idxs)} files exist"]

        print(f"[export_yz] var={var}  x_idxs={pending_idxs}  "
              f"chunk={chunk_gb} GB  stride={stride}", flush=True)

        field = utils_yz.open_lazy_yz(var, p, yz_chunk_mem_gb=chunk_gb)

        # Single-pass extraction of all requested slices
        slices = field.read_yz_multi(pending_idxs, stride=stride)

        written = []
        for x_idx in pending_idxs:
            fname = f"{p.name}_yz_x{x_idx}_st{st_tag}_{var}.nc"
            path = _write_yz_netcdf(
                arr2d    = slices[x_idx],
                p        = p,
                x_idx    = x_idx,
                stride   = stride,
                outdir   = outdir,
                fname    = fname,
                overwrite = overwrite,
            )
            print(f"[export_yz] wrote: {path}", flush=True)
            written.append(path)

        return written

    except Exception as e:
        import traceback
        return [f"ERROR var={var}: {e}\n{traceback.format_exc()}"]


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _evenly_spaced_indices(N: int, n: int):
    n = int(n)
    if n <= 1:
        return [N // 2]
    idxs = [int(round(k * N / (n + 1))) for k in range(1, n + 1)]
    idxs = [max(0, min(N - 1, i)) for i in idxs]
    out = []
    for i in idxs:
        if i not in out:
            out.append(i)
    return out


def parse_args():
    ap = argparse.ArgumentParser(
        description="Export yz slices for heavy DNS cases (one file-pass per variable)."
    )
    ap.add_argument("--case",    required=True, help="Case name, e.g. R8P7")
    ap.add_argument(
        "--vars", nargs="+", default=["u", "v", "w", "r", "ee", "chi"],
        help="Variables to export (default: u v w r ee chi)",
    )
    ap.add_argument("--nyz",    type=int, default=1,
                    help="Number of yz slices (evenly spaced in x, default 1)")
    ap.add_argument("--idx_yz", type=int, nargs="+", default=None,
                    help="Explicit x-indices for yz slices (overrides --nyz)")
    ap.add_argument("--stride", type=int, nargs=3, default=(1, 1, 1),
                    metavar=("SX", "SY", "SZ"),
                    help="Stride in x y z  (sx unused for yz, default 1 1 1)")
    ap.add_argument("--tstamp", default=None, help="Override tStamp")
    ap.add_argument("--outdir", default=None,
                    help="Output directory (default: <dirPath>/2D_slices)")
    ap.add_argument("--nproc",  type=int, default=1,
                    help="Worker processes (one per variable, default 1)")
    ap.add_argument(
        "--yz-chunk-mem-gb", type=float, default=18.0, dest="yz_chunk_mem_gb",
        help=(
            "RAM budget per worker (GB) for z-slab reads (default 18). "
            "Set to floor(available_RAM / nproc) minus ~2 GB margin. "
            "Each slab = (Nx+2)*Ny*4 bytes  "
            "(e.g. ~1.01 GB for R8P7, ~1.87 GB for R10P7)."
        ),
    )
    ap.add_argument("--overwrite", action="store_true",
                    help="Re-export files that already exist")
    return ap.parse_args()


def main():
    args = parse_args()

    p_main = build_case_from_csv(args.case, tstamp_override=args.tstamp)
    outdir = (Path(args.outdir) if args.outdir
              else Path(p_main.dirPath) / "2D_slices")
    outdir.mkdir(parents=True, exist_ok=True)

    vars_  = [v.strip() for v in args.vars]
    if not vars_:
        raise ValueError("No variables specified via --vars")

    # Resolve x-indices
    if args.idx_yz is not None:
        x_idxs = [int(i) for i in args.idx_yz]
    else:
        x_idxs = _evenly_spaced_indices(p_main.Nx, args.nyz)

    stride = tuple(args.stride)

    # Memory estimate
    bytes_per_z = (p_main.Nx + 2) * p_main.Ny * 4
    chunk_nz    = max(1, int(args.yz_chunk_mem_gb * 1024 ** 3) // bytes_per_z)
    slab_gb     = bytes_per_z * chunk_nz / 1024 ** 3
    total_slabs = -(-p_main.Nz // chunk_nz)   # ceil division

    print(f"[export_yz] case={p_main.name}  tStamp={p_main.tStamp}")
    print(f"[export_yz] grid: Nx={p_main.Nx}  Ny={p_main.Ny}  Nz={p_main.Nz}")
    print(f"[export_yz] outdir={outdir}")
    print(f"[export_yz] vars={vars_}  x_idxs={x_idxs}  stride={stride}")
    print(f"[export_yz] nproc={args.nproc}  yz_chunk_mem_gb={args.yz_chunk_mem_gb}")
    print(f"[export_yz] slab size ≈ {slab_gb:.2f} GB  "
          f"({total_slabs} slabs/variable, one file-pass)")
    print(f"[export_yz] peak RAM estimate ≈ "
          f"{args.nproc * args.yz_chunk_mem_gb:.0f} GB (workers) + overhead")
    print(f"[export_yz] {len(vars_)} tasks (one per variable)")
    print()

    if args.nproc <= 1 or len(vars_) == 1:
        _worker_init(args.case, args.tstamp, str(outdir), stride,
                     args.overwrite, args.yz_chunk_mem_gb, x_idxs)
        results = [_worker_run(v) for v in vars_]
    else:
        ctx = mp.get_context("spawn")
        with ctx.Pool(
            processes   = args.nproc,
            initializer = _worker_init,
            initargs    = (args.case, args.tstamp, str(outdir), stride,
                           args.overwrite, args.yz_chunk_mem_gb, x_idxs),
        ) as pool:
            results = pool.map(_worker_run, vars_)

    # Report
    n_ok = 0
    for r in results:
        if isinstance(r, list):
            for item in r:
                if isinstance(item, str) and item.startswith("ERROR"):
                    print(f"[export_yz] {item}", flush=True)
                else:
                    n_ok += 1
        else:
            print(f"[export_yz] unexpected result: {r}", flush=True)

    total = sum(len(r) for r in results if isinstance(r, list))
    print(f"[export_yz] done.  ({n_ok}/{total} successful)")


if __name__ == "__main__":
    main()
