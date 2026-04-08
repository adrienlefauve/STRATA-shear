#!/usr/bin/env python3
# A. Lefauve, 2026
"""
Load previously exported NetCDF slice files for one case, reconstruct the
derived (rescaled) plotting fields, and write summary/native-resolution figures.

Typical use:
    python load_netcdf_slices_and_plot_figures.py R1P1

By default this script:
- reads case parameters from <code_root>/params.csv
- looks for slice files under:
      <project_root>/<case>/001_Final/2D_slices
- caches the discovered slice-file structure in:
      <case>/001_Final/2D_slices/<case>_slices_cache.pkl
- selects one slice per plane (xy, xz, yz), choosing the available index
  closest to the mid-plane unless manually overridden
- requires the six exported variables:
      u, v, w, r, ee, chi
- reconstructs the normalised plotting fields used by utils.py:
      uN, vN, wN, bN, epslog, chilog
- writes summary figures and/or native-resolution figures into:
      <code_root>/figures/<case>

Notes:
- This script does not read the original large binary volumes; it only works
  from already exported (relatively lightweight) NetCDF slice files.
- It is intended as a lightweight post-processing step after slice export.
"""

from __future__ import annotations

import argparse
import importlib
import pickle
import re
import sys
from pathlib import Path
from types import SimpleNamespace

import matplotlib
matplotlib.use("Agg")
import numpy as np
import pandas as pd


DEFAULT_CODE_ROOT = Path("/ccs/home/lefauve/git/INCITE/adrien/")
DEFAULT_PROJECT_ROOT = Path("/lustre/orion/cfd135/proj-shared/Hsst")
REQUIRED_VARS = ("u", "v", "w", "r", "ee", "chi")


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(
        description="Load one case worth of NetCDF slices and plot/export the figures.",
    )
    ap.add_argument("case", help="Case name, e.g. R1P1")
    ap.add_argument(
        "--code-root",
        type=Path,
        default=DEFAULT_CODE_ROOT,
        help=f"Directory containing utils.py and params.csv (default: {DEFAULT_CODE_ROOT})",
    )
    ap.add_argument(
        "--project-root",
        type=Path,
        default=DEFAULT_PROJECT_ROOT,
        help=f"Root directory containing case folders (default: {DEFAULT_PROJECT_ROOT})",
    )
    ap.add_argument(
        "--csv-path",
        type=Path,
        default=None,
        help="Path to params.csv. Default: <code-root>/params.csv",
    )
    ap.add_argument(
        "--outdir",
        type=Path,
        default=None,
        help="Output directory for figures. Default: <code-root>/figures/<case>",
    )
    ap.add_argument(
        "--idx-xy",
        type=int,
        default=None,
        help="Manually choose the xy slice index. Default: nearest available to the mid-plane.",
    )
    ap.add_argument(
        "--idx-xz",
        type=int,
        default=None,
        help="Manually choose the xz slice index. Default: nearest available to the mid-plane.",
    )
    ap.add_argument(
        "--idx-yz",
        type=int,
        default=None,
        help="Manually choose the yz slice index. Default: nearest available to the mid-plane.",
    )
    ap.add_argument(
        "--refresh-cache",
        action="store_true",
        help="Ignore any existing slice-discovery cache and rebuild it.",
    )
    ap.add_argument(
        "--skip-summary",
        action="store_true",
        help="Skip the 3 summary figures (one per plane).",
    )
    ap.add_argument(
        "--skip-native",
        action="store_true",
        help="Skip the native-resolution exports (one figure per variable per plane).",
    )
    return ap.parse_args()


def import_utils(code_root: Path):
    code_root = code_root.resolve()
    if str(code_root) not in sys.path:
        sys.path.insert(0, str(code_root))
    import utils  # type: ignore
    importlib.reload(utils)
    return utils


def load_params(csv_path: Path) -> pd.DataFrame:
    df = pd.read_csv(csv_path, dtype={"tStamp": str})
    df.columns = [str(c).strip() for c in df.columns]
    return df


def build_case_from_csv(case_name: str, params_df: pd.DataFrame, project_root: Path, tstamp_override=None):
    row = params_df.loc[params_df["name"].astype(str).str.strip() == str(case_name).strip()]
    if row.empty:
        raise KeyError(
            f"Unknown case '{case_name}'. Available: {sorted(params_df['name'].astype(str).str.strip().tolist())}"
        )
    row = row.iloc[0]

    nx = int(float(row["Nx"]))
    lx = float(row["Lx"])

    p = SimpleNamespace()
    p.name = str(row["name"]).strip()
    p.tStamp = f"{float(tstamp_override):.6f}" if tstamp_override is not None else f"{float(row['tStamp']):.6f}"

    p.Nx = nx
    p.Ny = nx // 2
    p.Nz = nx // 4
    p.Lx = lx
    p.Ly = lx / 2.0
    p.Lz = lx / 4.0

    p.nu = float(row["nu"])
    p.Pr = float(row["Pr"])
    p.Ri = float(row["Ri"])
    p.Reb = float(row["Gn"])
    p.Ek = float(row["Ek"])
    p.Ep = float(row["Ep"])
    p.eps = float(row["ek"])
    p.chi = float(row["ep"])
    p.Gamma1 = float(row["Gamma1"])

    p.N2 = p.Ri
    p.N = float(np.sqrt(p.N2))

    p.dirPath = str(project_root / p.name / "001_Final") + "/"
    return p


def discover_var_slice_files(slice_dir: Path, case_name: str):
    patt = re.compile(
        rf"^{re.escape(case_name)}_(xy|xz|yz)_[xyz](\d+)_st(\d+)x(\d+)_([A-Za-z0-9]+)\.nc$"
    )
    files_by_plane = {"xy": {}, "xz": {}, "yz": {}}
    for path in sorted(slice_dir.glob(f"{case_name}_*.nc")):
        m = patt.match(path.name)
        if not m:
            continue
        if path.stat().st_size == 0:
            print(f"[skip] {path.name}: 0-byte file (still being written?)")
            continue
        pl, idx, _sx, _sy, var = m.groups()
        idx = int(idx)
        files_by_plane.setdefault(pl, {}).setdefault(idx, {})[var] = path
    return files_by_plane


def choose_index(varmap_by_idx, required_vars=REQUIRED_VARS, preferred=None):
    if preferred is not None and preferred in varmap_by_idx:
        miss = [v for v in required_vars if v not in varmap_by_idx[preferred]]
        if not miss:
            return preferred
    for idx in sorted(varmap_by_idx):
        miss = [v for v in required_vars if v not in varmap_by_idx[idx]]
        if not miss:
            return idx
    raise RuntimeError("No slice index has all required variables.")


def load_or_build_slice_cache(slice_dir: Path, case_name: str, refresh_cache: bool):
    cache_path = slice_dir / f"{case_name}_slices_cache.pkl"

    if cache_path.exists() and not refresh_cache:
        try:
            with open(cache_path, "rb") as f:
                files_by_plane = pickle.load(f)
            print(f"Loaded cached slice list: {cache_path}")
            return files_by_plane
        except Exception as e:
            print(f"Cache exists but could not be read ({e}), rescanning directory...")

    print("Scanning slice directory...")
    files_by_plane = discover_var_slice_files(slice_dir, case_name)
    with open(cache_path, "wb") as f:
        pickle.dump(files_by_plane, f)
    print(f"Saved cache: {cache_path}")
    return files_by_plane


def select_slice_paths(p, files_by_plane, idx_xy=None, idx_xz=None, idx_yz=None):
    preferred_idx = {"xy": idx_xy, "xz": idx_xz, "yz": idx_yz}
    target_idx = {"xy": p.Nz // 2, "xz": p.Ny // 2, "yz": p.Nx // 2}

    selected_idx = {}
    paths = {}

    for pl in ("xy", "xz", "yz"):
        if not files_by_plane.get(pl):
            continue

        try:
            if preferred_idx[pl] is not None:
                idx = choose_index(files_by_plane[pl], preferred=preferred_idx[pl])
            else:
                available = sorted(files_by_plane[pl].keys())
                idx = min(available, key=lambda i: abs(i - target_idx[pl]))
                if any(v not in files_by_plane[pl][idx] for v in REQUIRED_VARS):
                    idx = choose_index(files_by_plane[pl], preferred=idx)
        except RuntimeError as e:
            print(f"[skip] {pl}: {e}")
            continue

        selected_idx[pl] = idx
        paths[pl] = files_by_plane[pl][idx]

    return target_idx, selected_idx, paths


def load_raw_slices(utils, p, planes_ok, paths, selected_idx):
    raw2d = {}
    meta2d = {}

    for pl in planes_ok:
        raw2d[pl] = {}
        plane_meta = None

        for var in REQUIRED_VARS:
            if var not in paths[pl]:
                raise KeyError(f"Missing variable '{var}' for plane '{pl}' at index {selected_idx[pl]}")

            path = paths[pl][var]
            raw_one, meta_one = utils._read_plane_nc(path)

            if var not in raw_one:
                if len(raw_one) == 1:
                    only_key = next(iter(raw_one.keys()))
                    raw2d[pl][var] = raw_one[only_key]
                else:
                    raise KeyError(f"{path.name}: expected variable '{var}', found {list(raw_one.keys())}")
            else:
                raw2d[pl][var] = raw_one[var]

            plane_meta = meta_one

        meta2d[pl] = plane_meta

        u2 = raw2d[pl]["u"]
        v2 = raw2d[pl]["v"]
        w2 = raw2d[pl]["w"]
        ee2 = raw2d[pl]["ee"]
        chi2 = raw2d[pl]["chi"]

        ek_slice = float(np.mean(0.5 * (u2**2 + v2**2 + w2**2)))
        ee_slice = float(np.mean(ee2))
        chi_slice = float(np.mean(chi2))

        fixed = {"xy": "iz", "xz": "iy", "yz": "ix"}[pl]
        fixed_val = selected_idx[pl]
        print(
            f"[{pl}] {fixed}={fixed_val}  "
            f"Ek_slice={ek_slice:.6e}  "
            f"ee_slice={ee_slice:.6e}  chi_slice={chi_slice:.6e}"
        )

    ek_slice_mean = float(np.mean([
        np.mean(0.5 * (raw2d[pl]["u"]**2 + raw2d[pl]["v"]**2 + raw2d[pl]["w"]**2))
        for pl in raw2d
    ]))
    ep_slice_mean = float(np.mean([
        np.mean(1e6 * p.Ri / 2 * (raw2d[pl]["r"]**2))
        for pl in raw2d
    ]))
    eps_slice_mean = float(np.mean([
        float(np.mean(raw2d[pl]["ee"]))
        for pl in raw2d
    ]))
    chi_slice_mean = float(np.mean([
        float(np.mean(raw2d[pl]["chi"]))
        for pl in raw2d
    ]))

    print("\n[reference stats from params.csv]")
    print(f"  Ek:      {float(p.Ek):.6e}")
    print(f"  Ep:      {float(p.Ep):.6e}")
    print(f"  eps_avg: {float(p.eps):.6e}")
    print(f"  chi_avg: {float(p.chi):.6e}")

    print(f"\nMean 2D slice Ek is {ek_slice_mean / p.Ek * 100.0:.2f}% of 3D Ek")
    print(f"Mean 2D slice Ep is {ep_slice_mean / p.Ep * 100.0:.2f}% of 3D Ep")
    print(f"Mean 2D slice eps is {eps_slice_mean / p.eps * 100.0:.2f}% of 3D eps")
    print(f"Mean 2D slice chi is {chi_slice_mean / p.chi * 100.0:.2f}% of 3D chi")
    print(
        f"Mean 2D slice chi is {chi_slice_mean / (p.eps * p.Gamma1) * 100.0:.2f}% "
        f"of 3D chi inferred from eps and Gamma1"
    )

    return raw2d, meta2d


def build_slice_bundle(utils, p, raw2d, meta2d, selected_idx):
    out_vars = {name: utils.VarSlices(name) for name in ["uN", "vN", "wN", "bN", "epslog", "chilog"]}

    ek = float(p.Ek)
    ep = float(p.Ep)
    eps_avg = float(p.eps)
    chi_avg = float(p.eps * p.Gamma1)
    n2 = float(p.N2)
    tiny = 1e-30

    for pl in raw2d.keys():
        u2 = raw2d[pl]["u"]
        v2 = raw2d[pl]["v"]
        w2 = raw2d[pl]["w"]
        r2 = raw2d[pl]["r"]
        ee2 = raw2d[pl]["ee"]
        chi2 = raw2d[pl]["chi"]

        out_vars["uN"].set(pl, u2 / np.sqrt(ek))
        out_vars["vN"].set(pl, v2 / np.sqrt(ek))
        out_vars["wN"].set(pl, w2 / np.sqrt(ek))
        out_vars["bN"].set(pl, -1000.0 * p.Ri * r2 / np.sqrt(n2 * ep))

        with np.errstate(divide="ignore", invalid="ignore"):
            out_vars["epslog"].set(pl, np.log10(np.maximum(ee2, tiny) / eps_avg))
            out_vars["chilog"].set(pl, np.log10(np.maximum(chi2, tiny) / chi_avg))

    idx_map = {
        "xy": selected_idx.get("xy", -1),
        "xz": selected_idx.get("xz", -1),
        "yz": selected_idx.get("yz", -1),
    }

    first_pl = next(iter(meta2d.keys()))
    attrs = meta2d[first_pl].get("attrs", {}) if isinstance(meta2d[first_pl], dict) else {}
    stride_tuple = (
        int(attrs.get("stride_x", 1)),
        int(attrs.get("stride_y", 1)),
        int(attrs.get("stride_z", 1)),
    )

    s = utils.SliceBundle(vars=out_vars, idx=idx_map, stride=stride_tuple)
    print("planes:", s.available_planes())
    print("vars:", s.available_vars())
    return s


def main() -> None:
    args = parse_args()

    code_root = args.code_root.resolve()
    csv_path = args.csv_path.resolve() if args.csv_path is not None else (code_root / "params.csv")
    project_root = args.project_root.resolve()

    utils = import_utils(code_root)
    params_df = load_params(csv_path)
    p = build_case_from_csv(args.case, params_df, project_root)

    slice_dir = Path(p.dirPath) / "2D_slices"
    if not slice_dir.exists():
        raise FileNotFoundError(f"Slice directory not found: {slice_dir}")

    print(f"case      : {p.name}")
    print(f"slice_dir : {slice_dir}")
    print(f"csv_path  : {csv_path}")

    files_by_plane = load_or_build_slice_cache(slice_dir, p.name, args.refresh_cache)
    for pl in ("xy", "xz", "yz"):
        print(pl, "available indices:", sorted(files_by_plane.get(pl, {}).keys())[:20])

    target_idx, selected_idx, paths = select_slice_paths(
        p,
        files_by_plane,
        idx_xy=args.idx_xy,
        idx_xz=args.idx_xz,
        idx_yz=args.idx_yz,
    )

    print("target_idx  :", target_idx)
    print("selected_idx:", selected_idx)

    planes_ok = sorted(paths.keys())
    if not planes_ok:
        raise RuntimeError("No valid xy/xz/yz slices were found for this case.")
    print("planes_ok:", planes_ok)

    print("nu =", p.nu)
    print("Ri = N2 =", p.N2)
    print("Ek =", p.Ek)
    print("Ep =", p.Ep)
    print("eps =", p.eps)
    print("chi =", p.chi)

    raw2d, meta2d = load_raw_slices(utils, p, planes_ok, paths, selected_idx)
    s = build_slice_bundle(utils, p, raw2d, meta2d, selected_idx)

    fig_dir = args.outdir.resolve() if args.outdir is not None else (code_root / "figures" / p.name)
    fig_dir.mkdir(parents=True, exist_ok=True)
    print(f"fig_dir    : {fig_dir}")

    planes_avail = tuple(pl for pl in ("xy", "xz", "yz") if pl in s.available_planes())
    if not planes_avail:
        raise RuntimeError("No planes available in SliceBundle 's' (nothing to plot/export).")

    if not args.skip_summary:
        print("Writing summary figures...")
        utils.plot_slices_derived_bundle_multi(
            p,
            s,
            planes=planes_avail,
            save=True,
            outdir=str(fig_dir),
            fmt="png",
            dpi=300,
        )

    if not args.skip_native:
        print("Writing native-resolution figures...")
        paths_exported = []
        total = len(planes_avail)
        for i, plane in enumerate(planes_avail, 1):
            print(f"[{i}/{total}] Exporting plane: {plane}")
            exported = utils.export_native_resolution_from_bundle_multi(
                p,
                s,
                planes=[plane],
                outdir=str(fig_dir),
            )
            paths_exported.extend(exported)
        print(f"Wrote {len(paths_exported)} native-resolution figure files")

    print("Done.")


if __name__ == "__main__":
    main()
