#!/usr/bin/env python3
# A. Lefauve, 2026
"""
Unified 2D slice exporter — xy, xz, and yz planes in one script.

  python export_slices.py \\
      --case R8P7          \\
      --planes xy xz yz    \\
      --nxy 3 --nxz 3 --nyz 5 \\
      --vars u v w r ee chi \\
      --stride 1 1 1

PLANES
------
  xy / xz : memmap approach — x is the fast (contiguous) axis on disk, so
            reading an xy or xz slice is a sequential read.  Fast.
  yz      : the entire file must be read to extract a yz slice at fixed x,
            because x varies fastest (Fortran order) and yz data is scattered
            across the whole file.  The script avoids ~130 M random seeks by
            reading contiguous z-slabs into RAM and extracting x=idx there.

SLICE SELECTION
---------------
  By default, slices are evenly spaced across the domain:
    --nxy N  →  N z-indices evenly spaced in [0, Nz)
    --nxz N  →  N y-indices evenly spaced in [0, Ny)
    --nyz N  →  N x-indices evenly spaced in [0, Nx)

  To pick exact indices instead, use the override flags:
    --idx_xy IZ [IZ ...]  →  one or more z-indices (overrides --nxy)
    --idx_xz IY [IY ...]  →  one or more y-indices (overrides --nxz)
    --idx_yz IX [IX ...]  →  one or more x-indices (overrides --nyz)

  The override completely replaces the evenly-spaced list; they do not add
  together.  Example:
    --nyz 5 --idx_yz 1000 8000  →  only x=1000 and x=8000 are exported.

STRIDE
------
  --stride sx sy sz : subsample the output slice along each axis.
  1 1 1 = full resolution (standard for archival and analysis).
  For yz planes sx is IGNORED (x is the fixed axis); only sy and sz matter,
  so prefer "1 2 2" over "2 2 2" to make the intent explicit.

MEMORY & TUNING
---------------
  Available RAM is auto-detected as min(/proc/meminfo, SLURM_MEM_PER_NODE) × 0.90.

  xy / xz: memory footprint per worker is tiny (~one 2D slice).  nproc
    defaults to min(n_vars, 6); extra RAM does not help.  Use --mem=32G.

  yz: FEWER WORKERS = BIGGER SLABS = FASTER.  Lustre read-ahead is most
    effective with large sequential reads:
      2 workers × 100 GB/slab  ≈ 1380 MB/s total  ✓
      6 workers ×  34 GB/slab  ≈  560 MB/s total  ✗
    nproc is chosen as the smallest value giving >= 50 GB/slab.
    With --mem=220G → 3 workers × ~66 GB (auto).  Pass --nproc 2 to
    force 2 workers × ~99 GB for maximum throughput.
    On Andes: -c 2  --mem=220G  -t 24:00:00
    R8P7 reference: 5.7 TB/var, ~8 h for 2 vars at 2 workers.

SKIP LOGIC
----------
  Existing files are skipped unless --overwrite is passed.  Safe to rerun
  after a partial job — only missing files are written.

"""

import argparse
import os
import time
from pathlib import Path
import multiprocessing as mp
import pandas as pd
from types import SimpleNamespace

import numpy as np

import utils

print("[export_slices] starting", flush=True)

CSV_PATH     = Path("params.csv")
PROJECT_ROOT = Path("/lustre/orion/cfd135/proj-shared/Hsst")
PARAMS_DF    = pd.read_csv(CSV_PATH, dtype={"tStamp": str})
PARAMS_BY_CASE = {str(row["name"]).strip(): row for _, row in PARAMS_DF.iterrows()}

MIN_YZ_SLAB_GB = 50   # minimum slab size to get good Lustre read-ahead


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _detect_available_ram_gb(fraction: float = 0.90) -> float:
    """Return fraction × available RAM (Linux only).

    Takes the minimum of /proc/meminfo MemTotal and SLURM_MEM_PER_NODE
    (the job's allocation limit in MB), so the estimate never exceeds
    what SLURM will allow.  SLURM_MEM_PER_NODE=0 means unlimited — ignored.
    """
    node_gb = None
    try:
        with open("/proc/meminfo") as f:
            for line in f:
                if line.startswith("MemTotal:"):
                    node_gb = int(line.split()[1]) / 1024 ** 2
                    break
    except Exception:
        pass

    slurm_gb = None
    slurm_mem = os.environ.get("SLURM_MEM_PER_NODE")  # MB; 0 = unlimited
    if slurm_mem:
        try:
            v = int(slurm_mem)
            if v > 0:
                slurm_gb = v / 1024
        except ValueError:
            pass

    candidates = [x for x in (node_gb, slurm_gb) if x is not None]
    if candidates:
        return min(candidates) * fraction
    return 120.0   # safe fallback


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


def build_case_from_csv(case_name: str, tstamp_override=None):
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
    return p


# ---------------------------------------------------------------------------
# xy / xz worker  (unchanged logic from export_netcdf_slices_from_binary_3D.py)
# ---------------------------------------------------------------------------

_G: dict = {}

def _worker_init_xyxz(case_name, tstamp, outdir, stride, overwrite, stream):
    p = build_case_from_csv(case_name, tstamp_override=tstamp)
    outdir_p = Path(outdir)
    outdir_p.mkdir(parents=True, exist_ok=True)
    _G["p"]         = p
    _G["outdir"]    = outdir_p
    _G["stride"]    = tuple(stride)
    _G["overwrite"] = bool(overwrite)
    _G["stream"]    = bool(stream)
    _G["fields"]    = {}


def _get_field(var):
    if var not in _G["fields"]:
        _G["fields"][var] = utils.open_lazy_fields([var], _G["p"])
    return _G["fields"][var]


def _progress_cb(plane, idx):
    fixed = {"xy": "z", "xz": "y", "yz": "x"}[plane]
    def cb(var, i, n):
        pct = int(100 * i / max(1, n))
        print(f"[{plane} {fixed}{idx}] {var} ({pct}%)", flush=True)
    return cb


def _worker_run_xyxz(task: dict):
    try:
        plane = task["plane"]
        idx   = int(task["idx"])
        var   = task["var"]
        p     = _G["p"]
        outdir = _G["outdir"]
        stride = _G["stride"]
        overwrite = _G["overwrite"]
        stream    = _G["stream"]
        sx, sy, sz = stride
        fixed = {"xy": "z", "xz": "y"}[plane]
        st    = f"{sx}x{sy}" if plane == "xy" else f"{sx}x{sz}"
        fname = f"{p.name}_{plane}_{fixed}{idx}_st{st}_{var}.nc"
        path  = outdir / fname

        if path.exists() and not overwrite:
            print(f"[skip] {fname}", flush=True)
            return str(path)

        t0 = time.perf_counter()
        print(f"[{var}] {plane} {fixed}={idx}  stride={stride}", flush=True)
        utils.save_raw_plane_netcdf(
            fields=_get_field(var),
            p=p,
            plane=plane,
            idx=idx,
            outdir=outdir,
            stride=stride,
            fname=fname,
            verbose=True,
            stream=stream,
            progress_cb=_progress_cb(plane, idx),
            varnames=[var],
        )
        print(f"[{var}] wrote {fname}  ({time.perf_counter()-t0:.0f}s)", flush=True)
        return str(path)
    except Exception as e:
        import traceback
        return f"ERROR {task}: {e}\n{traceback.format_exc()}"


# ---------------------------------------------------------------------------
# yz worker  (slab-based, one worker per variable)
# ---------------------------------------------------------------------------

_GYZ: dict = {}

def _worker_init_yz(case_name, tstamp, outdir, stride, overwrite, chunk_gb):
    p = build_case_from_csv(case_name, tstamp_override=tstamp)
    outdir_p = Path(outdir)
    outdir_p.mkdir(parents=True, exist_ok=True)
    _GYZ["p"]         = p
    _GYZ["outdir"]    = outdir_p
    _GYZ["stride"]    = tuple(stride)
    _GYZ["overwrite"] = bool(overwrite)
    _GYZ["chunk_gb"]  = float(chunk_gb)


def _worker_run_yz(task: dict):
    """task: {"var": str, "x_idxs": [int, ...]}"""
    try:
        var     = task["var"]
        x_idxs  = task["x_idxs"]
        p       = _GYZ["p"]
        outdir  = _GYZ["outdir"]
        stride  = _GYZ["stride"]
        overwrite = _GYZ["overwrite"]
        chunk_gb  = _GYZ["chunk_gb"]
        _sx, sy, sz = stride
        st_tag = f"{sy}x{sz}"

        # skip logic
        pending = [xi for xi in x_idxs
                   if not (outdir / f"{p.name}_yz_x{xi}_st{st_tag}_{var}.nc").exists()
                   or overwrite]
        if not pending:
            print(f"[{var}] all yz files exist — skipping", flush=True)
            return [f"[skip] {var}"]

        bytes_per_z = (p.Nx + 2) * p.Ny * 4
        chunk_nz    = max(1, int(chunk_gb * 1024**3) // bytes_per_z)
        n_slabs     = -(-p.Nz // chunk_nz)
        file_gb     = (p.Nx + 2) * p.Ny * p.Nz * 4 / 1024**3
        print(f"[{var}] yz  x_idxs={pending}  file={file_gb:.2f} GB  "
              f"chunk={chunk_gb:.1f} GB ({chunk_nz} z-planes/slab, {n_slabs} slabs)",
              flush=True)

        t0    = time.perf_counter()
        field = utils.open_lazy_yz(var, p, yz_chunk_mem_gb=chunk_gb)
        slices = field.read_yz_multi(pending, stride=stride, verbose=True, label=var)
        t_read = time.perf_counter()
        print(f"[{var}] read done  {t_read-t0:.0f}s", flush=True)

        written = []
        for xi in pending:
            fname = f"{p.name}_yz_x{xi}_st{st_tag}_{var}.nc"
            path  = utils.write_yz_netcdf(
                arr2d=slices[xi], varname=var, p=p, x_idx=xi,
                stride=stride, outdir=outdir, fname=fname, overwrite=overwrite,
            )
            print(f"[{var}] wrote {fname}  (+{time.perf_counter()-t_read:.1f}s)", flush=True)
            written.append(path)

        print(f"[{var}] total {time.perf_counter()-t0:.0f}s", flush=True)
        return written

    except Exception as e:
        import traceback
        return [f"ERROR var={task.get('var')}: {e}\n{traceback.format_exc()}"]


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def parse_args():
    ap = argparse.ArgumentParser(
        description="Export 2D slices (xy/xz/yz) from DNS binary files to NetCDF."
    )
    ap.add_argument("--case",    required=True)
    ap.add_argument("--planes",  nargs="+", default=["xy","xz","yz"],
                    help="Planes to export: xy xz yz (default: all three)")
    ap.add_argument("--vars",    nargs="+", default=["u","v","w","r","ee","chi"])
    ap.add_argument("--nxy",     type=int, default=1,
                    help="Number of xy slices (evenly spaced in z, default 1)")
    ap.add_argument("--nxz",     type=int, default=1,
                    help="Number of xz slices (evenly spaced in y, default 1)")
    ap.add_argument("--nyz",     type=int, default=1,
                    help="Number of yz slices (evenly spaced in x, default 1)")
    ap.add_argument("--idx_xy",  type=int, nargs="+", default=None, help="Explicit z-index(es) for xy plane")
    ap.add_argument("--idx_xz",  type=int, nargs="+", default=None, help="Explicit y-index(es) for xz plane")
    ap.add_argument("--idx_yz",  type=int, nargs="+", default=None,
                    help="Explicit x-index(es) for yz plane")
    ap.add_argument("--stride",  type=int, nargs=3, default=(1,1,1),
                    metavar=("SX","SY","SZ"))
    ap.add_argument("--tstamp",  default=None)
    ap.add_argument("--outdir",  default=None)
    ap.add_argument("--nproc",   type=int, default=None,
                    help="Override number of workers (default: auto)")
    ap.add_argument("--overwrite", action="store_true")
    ap.add_argument("--stream",    action="store_true",
                    help="Stream writes for xy/xz (lower peak RAM)")
    return ap.parse_args()


def main():
    args   = parse_args()
    planes = [pl.lower() for pl in args.planes]
    for pl in planes:
        if pl not in {"xy", "xz", "yz"}:
            raise ValueError(f"Unknown plane '{pl}'")

    p_main = build_case_from_csv(args.case, tstamp_override=args.tstamp)
    outdir = (Path(args.outdir) if args.outdir
              else Path(p_main.dirPath) / "2D_slices")
    outdir.mkdir(parents=True, exist_ok=True)

    vars_  = [v.strip() for v in args.vars]
    stride = tuple(args.stride)

    # -----------------------------------------------------------------------
    # Index lists
    # -----------------------------------------------------------------------
    idx_by_plane = {
        "xy": _evenly_spaced_indices(p_main.Nz, args.nxy),
        "xz": _evenly_spaced_indices(p_main.Ny, args.nxz),
        "yz": _evenly_spaced_indices(p_main.Nx, args.nyz),
    }
    if args.idx_xy is not None: idx_by_plane["xy"] = [int(i) for i in args.idx_xy]
    if args.idx_xz is not None: idx_by_plane["xz"] = [int(i) for i in args.idx_xz]
    if args.idx_yz is not None: idx_by_plane["yz"] = [int(i) for i in args.idx_yz]

    # -----------------------------------------------------------------------
    # Auto RAM detection
    # -----------------------------------------------------------------------
    avail_gb = _detect_available_ram_gb(fraction=0.90)

    # yz: minimise nproc to maximise slab size (better Lustre throughput)
    n_yz_vars = len(vars_)
    if args.nproc is not None:
        nproc_yz = args.nproc
    else:
        nproc_yz = max(1, min(n_yz_vars, int(avail_gb // MIN_YZ_SLAB_GB)))
    chunk_gb_yz = avail_gb / nproc_yz

    # xy/xz: tiny RAM per worker; use as many workers as there are tasks
    # (n_planes × n_slices × n_vars), capped at the number of available cores.
    n_xyxz_planes = sum(1 for pl in planes if pl in ("xy", "xz"))
    n_xyxz_tasks  = n_xyxz_planes * max(args.nxy, args.nxz) * len(vars_)
    n_cores       = int(os.environ.get("SLURM_CPUS_PER_TASK", os.cpu_count() or 1))
    nproc_xyxz    = args.nproc if args.nproc is not None else min(n_xyxz_tasks, n_cores)

    # -----------------------------------------------------------------------
    # Summary
    # -----------------------------------------------------------------------
    print(f"[export_slices] case={p_main.name}  tStamp={p_main.tStamp}")
    print(f"[export_slices] grid: Nx={p_main.Nx}  Ny={p_main.Ny}  Nz={p_main.Nz}")
    print(f"[export_slices] outdir={outdir}")
    print(f"[export_slices] planes={planes}  vars={vars_}  stride={stride}")
    print(f"[export_slices] idx: xy(iz)={idx_by_plane['xy']}  "
          f"xz(iy)={idx_by_plane['xz']}  yz(ix)={idx_by_plane['yz']}")
    print(f"[export_slices] detected RAM ≈ {avail_gb:.0f} GB")
    if "yz" in planes:
        bytes_per_z = (p_main.Nx + 2) * p_main.Ny * 4
        chunk_nz = max(1, int(chunk_gb_yz * 1024**3) // bytes_per_z)
        n_slabs  = -(-p_main.Nz // chunk_nz)
        print(f"[export_slices] yz: {nproc_yz} workers × {chunk_gb_yz:.1f} GB/slab "
              f"({chunk_nz} z-planes/slab, {n_slabs} slabs/variable)")
    if any(pl in planes for pl in ("xy","xz")):
        print(f"[export_slices] xy/xz: {nproc_xyxz} workers")
    print()

    t_job = time.perf_counter()

    # -----------------------------------------------------------------------
    # xy and xz export
    # -----------------------------------------------------------------------
    xyxz_planes = [pl for pl in planes if pl in ("xy", "xz")]
    if xyxz_planes:
        xyxz_tasks = [
            {"plane": pl, "idx": idx, "var": var}
            for pl in xyxz_planes
            for idx in idx_by_plane[pl]
            for var in vars_
        ]
        print(f"[export_slices] xy/xz: {len(xyxz_tasks)} tasks", flush=True)
        if nproc_xyxz <= 1 or len(xyxz_tasks) == 1:
            _worker_init_xyxz(args.case, args.tstamp, str(outdir), stride,
                              args.overwrite, args.stream)
            xyxz_results = [_worker_run_xyxz(t) for t in xyxz_tasks]
        else:
            ctx = mp.get_context("spawn")
            with ctx.Pool(
                processes=nproc_xyxz,
                initializer=_worker_init_xyxz,
                initargs=(args.case, args.tstamp, str(outdir), stride,
                          args.overwrite, args.stream),
            ) as pool:
                xyxz_results = pool.map(_worker_run_xyxz, xyxz_tasks)
        _report(xyxz_results, "xy/xz")

    # -----------------------------------------------------------------------
    # yz export  (one task per variable, each task handles all x_idxs)
    # -----------------------------------------------------------------------
    if "yz" in planes:
        x_idxs = idx_by_plane["yz"]
        yz_tasks = [{"var": var, "x_idxs": x_idxs} for var in vars_]
        print(f"[export_slices] yz: {len(yz_tasks)} tasks (one per variable)", flush=True)
        if nproc_yz <= 1 or len(yz_tasks) == 1:
            _worker_init_yz(args.case, args.tstamp, str(outdir), stride,
                            args.overwrite, chunk_gb_yz)
            yz_results = [_worker_run_yz(t) for t in yz_tasks]
        else:
            ctx = mp.get_context("spawn")
            with ctx.Pool(
                processes=nproc_yz,
                initializer=_worker_init_yz,
                initargs=(args.case, args.tstamp, str(outdir), stride,
                          args.overwrite, chunk_gb_yz),
            ) as pool:
                yz_results = pool.map(_worker_run_yz, yz_tasks)
        _report(yz_results, "yz")

    print(f"\n[export_slices] all done.  total elapsed {time.perf_counter()-t_job:.0f}s",
          flush=True)


def _report(results, label):
    n_ok = 0
    for r in results:
        items = r if isinstance(r, list) else [r]
        for item in items:
            if isinstance(item, str) and item.startswith("ERROR"):
                print(f"[export_slices/{label}] {item}", flush=True)
            else:
                n_ok += 1
    total = sum(len(r) if isinstance(r, list) else 1 for r in results)
    print(f"[export_slices/{label}] {n_ok}/{total} successful", flush=True)


if __name__ == "__main__":
    main()
