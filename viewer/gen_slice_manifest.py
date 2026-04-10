#!/usr/bin/env python3
# A. Lefauve, 2026
"""
gen_slice_manifest.py — Scan PNG snapshots and write slice_manifest.json
                        for use by slice_viewer/index.html.

Run this after tile_images.py has finished.

Usage:
    python gen_slice_manifest.py                          # uses defaults below
    python gen_slice_manifest.py \\
        --snapshots /path/to/snapshots \\
        --out-dir   /path/to/slice_viewer

Output:
    <out-dir>/slice_manifest.json
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Defaults
# ---------------------------------------------------------------------------
SNAPSHOTS_DEFAULT = Path(
    "/Users/adrien/Library/CloudStorage/"
    "Dropbox-Personal/Work/Office/Writings/Papers/"
    "027_2026_SHASSST/DATA/snapshots"
)
OUT_DEFAULT = Path(__file__).resolve().parent / "slice_viewer"

# ---------------------------------------------------------------------------
# Labels / ordering
# ---------------------------------------------------------------------------
VAR_LABELS = {
    "u":             "u — streamwise velocity",
    "v":             "v — spanwise velocity",
    "w":             "w — vertical velocity",
    "b":             "b — buoyancy",
    "e":             "ε — TKE dissipation",
    "c":             "χ — scalar dissipation",
    "all_variables": "All variables (summary)",
}

SLICE_LABELS = {
    "x": "yz-plane  (x = {idx})",
    "y": "xz-plane  (y = {idx})",
    "z": "xy-plane  (z = {idx})",
}

VAR_ORDER = ["all_variables", "u", "v", "w", "b", "e", "c"]

# ---------------------------------------------------------------------------
# Filename patterns — same as tile_images.py
# ---------------------------------------------------------------------------
_PATT_NATIVE = re.compile(
    r"^(?P<case>[A-Z0-9]+)_(?P<var>[a-z])_native_res_(?P<slice>[xyz]\d+)\.png$"
)
_PATT_ALL = re.compile(
    r"^(?P<case>[A-Z0-9]+)_all_variables_(?P<slice>[xyz]\d+)\.png$"
)


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="Generate slice_manifest.json from PNG snapshots.")
    ap.add_argument("--snapshots", type=Path, default=SNAPSHOTS_DEFAULT,
                    help=f"Snapshots root directory (default: {SNAPSHOTS_DEFAULT})")
    ap.add_argument("--out-dir", type=Path, default=OUT_DEFAULT,
                    help=f"Output directory for slice_manifest.json (default: {OUT_DEFAULT})")
    return ap.parse_args()


def main() -> None:
    args = parse_args()

    if not args.snapshots.exists():
        sys.exit(f"Snapshots directory not found: {args.snapshots}\n"
                 "Pass --snapshots /path/to/dir")

    entries = []
    for case_dir in sorted(args.snapshots.iterdir()):
        if not case_dir.is_dir():
            continue
        for png in sorted(case_dir.glob("*.png")):
            m = _PATT_NATIVE.match(png.name) or _PATT_ALL.match(png.name)
            if not m:
                continue
            var   = m.groupdict().get("var") or "all_variables"
            case  = m.group("case")
            sl    = m.group("slice")
            axis  = sl[0]
            idx   = sl[1:]
            key   = f"{var}_{sl}"
            entries.append({
                "case":        case,
                "var":         var,
                "var_label":   VAR_LABELS.get(var, var),
                "var_order":   VAR_ORDER.index(var) if var in VAR_ORDER else 99,
                "slice":       sl,
                "slice_label": SLICE_LABELS.get(axis, axis).format(idx=idx),
                "dzi":         f"{case}/{key}.dzi",
            })

    if not entries:
        sys.exit(f"No matching PNGs found in {args.snapshots}")

    args.out_dir.mkdir(parents=True, exist_ok=True)
    out = args.out_dir / "slice_manifest.json"
    out.write_text(json.dumps({"images": entries}, indent=2))

    print(f"Wrote {len(entries)} entries → {out}")


if __name__ == "__main__":
    main()
