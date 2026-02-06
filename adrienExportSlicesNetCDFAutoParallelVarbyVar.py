#!/usr/bin/env python3
"""
Export raw 2D slices to NetCDF, variable-by-variable (task = plane + idx + var).

Each export task writes ONE variable on ONE plane at ONE index to its own NetCDF file,
so that many cores can work independently (ideal for a full node).

Parallelisation model:
- process-based parallelism (multiprocessing spawn)
- each worker opens the case once
- each worker opens lazy fields per variable on demand and caches them

Typical call (example):
  python adrienExportSlicesNetCDFAutoParallelVarbyVar.py \
    --case R1P1 --planes xy xz \
    --vars u v w r ee chi \
    --nxy 5 --nxz 5 --nproc 30 \
    --stride 1 1 1 --stream --overwrite
"""

import argparse
from pathlib import Path
import multiprocessing as mp

import adrienParamClassSheared as params
import adrienUtils as utils

print("[adrienExportSlicesNetCDFParallelVarByVar] starting")

# -------------------------------------------------
# Worker globals (each process gets its own copy)
# -------------------------------------------------
_G = {}

def _worker_init(case_name: str, tstamp, outdir: str, stride, overwrite: bool, stream: bool):
    """
    Runs once per worker process.
    Opens the case inside the worker (safe for HPC + spawn).
    Lazy fields are opened per-variable on demand and cached.
    """
    cases = params.generate()
    if case_name not in cases:
        raise KeyError(f"Unknown case '{case_name}'. Available: {list(cases.keys())}")

    p = cases[case_name]
    if tstamp is not None:
        p.tStamp = tstamp

    outdir_p = Path(outdir)
    outdir_p.mkdir(parents=True, exist_ok=True)

    _G["p"] = p
    _G["outdir"] = outdir_p
    _G["stride"] = tuple(stride)
    _G["overwrite"] = overwrite
    _G["stream"] = stream

    # cache of lazy fields keyed by variable name
    _G["fields_by_var"] = {}


def _get_fields_for_var(var: str):
    """
    Open lazy fields for a single variable, cached per worker.
    """
    var = str(var)
    fbv = _G["fields_by_var"]
    if var not in fbv:
        fbv[var] = utils.open_lazy_fields([var], _G["p"])
    return fbv[var]


def progress_cb_factory(plane, idx):
    fixed_axis = {"xy": "z", "xz": "y", "yz": "x"}[plane]
    def cb(var, i, n):
        pct = int(100 * i / max(1, n))
        print(f"[{plane} {fixed_axis}{idx}] {var} ({pct}%)", flush=True)
    return cb


def export_one_var_slice(*, var: str, fields, p, plane: str, idx: int, outdir, stride=(1, 1, 1), overwrite=False, stream=True):
    """
    Write ONE variable on ONE plane at ONE index to a NetCDF file.
    """
    plane = plane.lower()
    var = str(var)
    fixed_axis = {"xy": "z", "xz": "y", "yz": "x"}[plane]
    sx, sy, sz = stride

    if plane == "xy":
        st = f"{sx}x{sy}"
    elif plane == "xz":
        st = f"{sx}x{sz}"
    elif plane == "yz":
        st = f"{sy}x{sz}"
    else:
        raise ValueError(f"Bad plane '{plane}'")

    # include var in filename to keep files independent and collision-free
    fname = f"{p.name}_{plane}_{fixed_axis}{idx}_st{st}_{var}.nc"
    path = outdir / fname

    if path.exists() and not overwrite:
        print(f"[skip] {path.name} exists", flush=True)
        return str(path)

    print(f"[export] {p.name} var={var} plane={plane} {fixed_axis}{idx} stride={stride}", flush=True)

    # Reuse existing writer: pass fields containing ONLY this var
    utils.save_raw_plane_netcdf(
        fields=fields,
        p=p,
        plane=plane,
        idx=idx,
        outdir=outdir,
        stride=stride,
        fname=fname,
        verbose=True,
        stream=stream,
        progress_cb=progress_cb_factory(plane, idx),
        varnames=[var],         # NEW
    )

    return str(path)


def _worker_run_task(task: dict):
    """
    task: {"plane": "xz", "idx": 3072, "var": "u"}
    Uses worker globals for p/outdir/stride/overwrite/stream.
    """
    try:
        var = task["var"]
        fields = _get_fields_for_var(var)
        return export_one_var_slice(
            var=var,
            fields=fields,
            p=_G["p"],
            plane=task["plane"],
            idx=int(task["idx"]),
            outdir=_G["outdir"],
            stride=_G["stride"],
            overwrite=_G["overwrite"],
            stream=_G["stream"],
        )
    except Exception as e:
        return f"ERROR plane={task.get('plane')} idx={task.get('idx')} var={task.get('var')}: {e}"


def parse_args():
    ap = argparse.ArgumentParser(
        description="Export raw 2D slices variable-by-variable to NetCDF for given case/planes."
    )
    ap.add_argument("--case", required=True, help="Case name, e.g. R1P1, R4P7, R10P1 ...")
    ap.add_argument("--planes", nargs="+", default=["xy", "xz", "yz"], help="Planes to export, subset of: xy xz yz")
    ap.add_argument(
        "--vars",
        nargs="+",
        default=["u", "v", "w", "r", "ee", "chi"],
        help="Variables to export (default: u v w r ee chi)",
    )
    ap.add_argument("--outdir", default=None, help="Output dir (default: <case dirPath>/2D_slices)")
    ap.add_argument("--stride", nargs=3, type=int, default=(1, 1, 1), metavar=("SX", "SY", "SZ"), help="Stride in x y z")
    ap.add_argument("--tstamp", default=None, help="Override tStamp (default uses case param)")
    ap.add_argument("--idx_xy", type=int, default=None, help="Index for xy plane (fixed z)")
    ap.add_argument("--idx_xz", type=int, default=None, help="Index for xz plane (fixed y)")
    ap.add_argument("--idx_yz", type=int, default=None, help="Index for yz plane (fixed x)")
    ap.add_argument("--overwrite", action="store_true", help="Overwrite existing files if present")
    ap.add_argument("--stream", action="store_true", help="Stream write (lower peak RAM)")
    ap.add_argument("--nxy", type=int, default=1, help="Number of xy slices to export (evenly spaced, default 1)")
    ap.add_argument("--nxz", type=int, default=1, help="Number of xz slices to export (evenly spaced, default 1)")
    ap.add_argument("--nyz", type=int, default=1, help="Number of yz slices to export (evenly spaced, default 1)")
    ap.add_argument("--nproc", type=int, default=1, help="Parallel workers (default 1 = serial)")
    return ap.parse_args()


def main():
    args = parse_args()

    # Resolve case once in main process for metadata/idx defaults + outdir default
    cases = params.generate()
    if args.case not in cases:
        raise KeyError(f"Unknown case '{args.case}'. Available: {list(cases.keys())}")

    p_main = cases[args.case]
    if args.tstamp is not None:
        p_main.tStamp = args.tstamp

    outdir = Path(args.outdir) if args.outdir else (Path(p_main.dirPath) / "2D_slices")
    outdir.mkdir(parents=True, exist_ok=True)

    planes = [pl.lower() for pl in args.planes]
    for pl in planes:
        if pl not in {"xy", "xz", "yz"}:
            raise ValueError(f"Bad plane '{pl}'. Use subset of: xy xz yz")

    vars_ = [v.strip() for v in args.vars]
    if len(vars_) == 0:
        raise ValueError("No variables requested via --vars")

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

    idx_list_by_plane = {
        "xy": _evenly_spaced_indices(p_main.Nz, args.nxy),
        "xz": _evenly_spaced_indices(p_main.Ny, args.nxz),
        "yz": _evenly_spaced_indices(p_main.Nx, args.nyz),
    }

    # manual overrides take precedence (single slice)
    if args.idx_xy is not None: idx_list_by_plane["xy"] = [int(args.idx_xy)]
    if args.idx_xz is not None: idx_list_by_plane["xz"] = [int(args.idx_xz)]
    if args.idx_yz is not None: idx_list_by_plane["yz"] = [int(args.idx_yz)]

    print(f"[export_slices] case={p_main.name} tStamp={p_main.tStamp}")
    print(f"[export_slices] outdir={outdir}")
    print(f"[export_slices] stride={tuple(args.stride)} planes={planes} vars={vars_}")
    print(f"[export_slices] idx lists: "
          f"xy(iz)={idx_list_by_plane['xy']} "
          f"xz(iy)={idx_list_by_plane['xz']} "
          f"yz(ix)={idx_list_by_plane['yz']}")
    print(f"[export_slices] nproc={args.nproc}")

    # Build variable-by-variable tasks
    tasks = []
    for pl in planes:
        for idx in idx_list_by_plane[pl]:
            for var in vars_:
                tasks.append({"plane": pl, "idx": idx, "var": var})
    print(f"[export_slices] {len(tasks)} var-by-var tasks")

    if args.nproc <= 1 or len(tasks) == 1:
        _worker_init(args.case, args.tstamp, str(outdir), tuple(args.stride), args.overwrite, args.stream)
        results = [_worker_run_task(t) for t in tasks]
    else:
        ctx = mp.get_context("spawn")
        with ctx.Pool(
            processes=args.nproc,
            initializer=_worker_init,
            initargs=(args.case, args.tstamp, str(outdir), tuple(args.stride), args.overwrite, args.stream),
        ) as pool:
            results = pool.map(_worker_run_task, tasks)

    # Report
    n_ok = 0
    for r in results:
        if isinstance(r, str) and r.startswith("ERROR"):
            print(f"[export_slices] {r}", flush=True)
        else:
            n_ok += 1
            print(f"[export_slices] wrote: {r}", flush=True)

    print(f"[export_slices] done. ({n_ok}/{len(results)} successful)")


if __name__ == "__main__":
    main()