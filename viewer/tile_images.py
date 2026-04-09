#!/usr/bin/env python3
# A. Lefauve, 2026
"""
tile_images.py — Pre-tile all PNG snapshots into Deep Zoom Image (DZI) pyramids
                 for lossless, Google-Maps-style viewing via OpenSeadragon.

Usage:
    brew install vips           # one-time dependency
    python tile_images.py       # uses default paths below

    # Or with explicit paths:
    python tile_images.py \\
        --snapshots /path/to/snapshots \\
        --out       /path/to/output/viewer

Outputs:
    <out>/manifest.json              — image catalogue read by index.html
    <out>/tiles/<case>/<key>.dzi     — zoom-level descriptor (XML, tiny)
    <out>/tiles/<case>/<key>_files/  — JPEG tile pyramid

To preview locally after tiling:
    cd <out> && python -m http.server 8000
    open http://localhost:8000

To deploy (one option — Cloudflare R2 free tier, 10 GB storage, no egress fee):
    1. Create a Cloudflare R2 bucket and enable public access
    2. Set bucket CORS to allow GET from your viewer's origin
    3. rclone sync <out>/tiles r2:<bucket>/tiles
    4. Edit BASE_URL in index.html to point to the bucket public URL
    5. Host index.html + manifest.json on GitHub Pages (or any static host)

MEMORY & TUNING
---------------
  vips streams the image rather than loading it fully; even 30000×15000 PNGs
  use only ~200 MB RAM.  Tiling one such image takes 5–15 s on a modern Mac.
  Use --skip-existing to resume a partially completed run.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# User-editable defaults
# ---------------------------------------------------------------------------
SNAPSHOTS_DEFAULT = Path(
    "/Users/adrien/Library/CloudStorage/"
    "Dropbox-Personal/Work/Office/Writings/Papers/"
    "027_2026_SHASSST/DATA/snapshots"
)
OUT_DEFAULT = Path(__file__).resolve().parent / "viewer"

# ---------------------------------------------------------------------------
# Display labels
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

# Variable display order in dropdown
VAR_ORDER = ["all_variables", "u", "v", "w", "b", "e", "c"]

# ---------------------------------------------------------------------------
# Filename patterns
# ---------------------------------------------------------------------------
# Matches: R10P7_u_native_res_x15840.png
_PATT_NATIVE = re.compile(
    r"^(?P<case>[A-Z0-9]+)_(?P<var>[a-z])_native_res_(?P<slice>[xyz]\d+)\.png$"
)
# Matches: R10P7_all_variables_x15840.png
_PATT_ALL = re.compile(
    r"^(?P<case>[A-Z0-9]+)_all_variables_(?P<slice>[xyz]\d+)\.png$"
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(
        description="Tile PNG snapshots into DZI pyramids for deep-zoom viewing."
    )
    ap.add_argument("--snapshots", type=Path, default=SNAPSHOTS_DEFAULT,
                    help=f"Snapshots root directory (default: {SNAPSHOTS_DEFAULT})")
    ap.add_argument("--out", type=Path, default=OUT_DEFAULT,
                    help=f"Output directory (default: {OUT_DEFAULT})")
    ap.add_argument("--tile-size", type=int, default=256,
                    help="Tile size in pixels (default: 256)")
    ap.add_argument("--quality", type=int, default=85,
                    help="JPEG tile quality 0–100 (default: 85)")
    ap.add_argument("--skip-existing", action="store_true",
                    help="Skip tiling if the .dzi already exists")
    return ap.parse_args()


def find_pngs(snapshots: Path) -> list[dict]:
    """Walk the snapshots directory and collect all parseable PNGs."""
    images = []
    for case_dir in sorted(snapshots.iterdir()):
        if not case_dir.is_dir():
            continue
        for png in sorted(case_dir.glob("*.png")):
            m = _PATT_NATIVE.match(png.name) or _PATT_ALL.match(png.name)
            if not m:
                continue
            var = m.groupdict().get("var") or "all_variables"
            images.append({
                "case":  m.group("case"),
                "var":   var,
                "slice": m.group("slice"),
                "path":  png,
            })
    return images


def tile_one(
    png: Path,
    out_stem: Path,
    tile_size: int,
    quality: int,
    skip_existing: bool,
) -> bool:
    """Run `vips dzsave` on a single PNG. Returns True if tiling was done."""
    dzi = out_stem.with_suffix(".dzi")
    if skip_existing and dzi.exists():
        print(f"  [skip]  {dzi.parent.name}/{dzi.name} (exists)")
        return False

    out_stem.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        "vips", "dzsave",
        str(png),
        str(out_stem),
        f"--tile-size={tile_size}",
        "--overlap=1",
        f"--suffix=.jpg[Q={quality}]",
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"  [ERROR] {png.name}: {result.stderr.strip()}", file=sys.stderr)
        return False
    return True


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    args = parse_args()

    if not shutil.which("vips"):
        sys.exit("vips not found. Install with:  brew install vips")

    if not args.snapshots.exists():
        sys.exit(f"Snapshots directory not found: {args.snapshots}\n"
                 "Pass --snapshots /path/to/dir")

    images = find_pngs(args.snapshots)
    if not images:
        sys.exit(f"No matching PNGs found in {args.snapshots}")

    print(f"Found {len(images)} images in {args.snapshots}")
    print(f"Output → {args.out}\n")

    tiles_dir = args.out / "tiles"
    manifest_entries = []
    done = skipped = errors = 0

    for img in images:
        case, var, sl = img["case"], img["var"], img["slice"]
        key     = f"{var}_{sl}"                     # e.g. u_x15840
        out_stem = tiles_dir / case / key

        axis  = sl[0]
        idx   = sl[1:]
        slice_label = SLICE_LABELS.get(axis, axis).format(idx=idx)
        var_label   = VAR_LABELS.get(var, var)
        var_order   = VAR_ORDER.index(var) if var in VAR_ORDER else 99

        print(f"[{case}]  {var_label}  /  {slice_label}")
        ok = tile_one(img["path"], out_stem, args.tile_size, args.quality,
                      args.skip_existing)
        if ok is True:
            done += 1
        elif ok is False and out_stem.with_suffix(".dzi").exists():
            skipped += 1
        else:
            errors += 1

        manifest_entries.append({
            "case":        case,
            "var":         var,
            "var_label":   var_label,
            "var_order":   var_order,
            "slice":       sl,
            "slice_label": slice_label,
            "dzi":         f"tiles/{case}/{key}.dzi",
        })

    # Write manifest
    manifest_path = args.out / "manifest.json"
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps({"images": manifest_entries}, indent=2))

    # Copy viewer HTML into the output directory
    html_src = Path(__file__).resolve().parent / "viewer" / "index.html"
    html_dst = args.out / "index.html"
    if html_src.exists() and html_src.resolve() != html_dst.resolve():
        shutil.copy(html_src, html_dst)
        print(f"\nCopied viewer  → {html_dst}")

    print(f"\n{'─'*50}")
    print(f"Tiled:   {done}   Skipped: {skipped}   Errors: {errors}")
    print(f"Manifest → {manifest_path}  ({len(manifest_entries)} entries)")
    print(f"\nTo preview locally:")
    print(f"  cd \"{args.out}\"  &&  python -m http.server 8000")
    print(f"  open http://localhost:8000")


if __name__ == "__main__":
    main()
