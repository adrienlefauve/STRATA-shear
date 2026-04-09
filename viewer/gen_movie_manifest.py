#!/usr/bin/env python3
"""
gen_movie_manifest.py
Scan a directory of cube MP4 movies and generate movie_manifest.json
for use by movie_viewer/index.html.

Expected file layout:
  <movies_dir>/<case>/<case>_<variable>_<axis>.mp4
  e.g.:  R4P7/R4P7_r_x.mp4

Usage:
  python gen_movie_manifest.py [--movies-dir PATH] [--out-dir PATH]

Defaults:
  --movies-dir  ~/Library/CloudStorage/Dropbox-Personal/Work/Office/Writings/
                Papers/027_2026_SHASSST/DATA/cube-movies
  --out-dir     ./movie_viewer
"""

import argparse
import json
import re
import sys
from pathlib import Path

DEFAULT_MOVIES_DIR = (
    Path.home()
    / "Library/CloudStorage/Dropbox-Personal/Work/Office/Writings"
    / "Papers/027_2026_SHASSST/DATA/cube-movies"
)
DEFAULT_OUT_DIR = Path(__file__).parent / "movie_viewer"

def natural_key(s):
    """Sort key that handles embedded numbers (R1 < R4 < R10)."""
    return [int(t) if t.isdigit() else t for t in re.split(r"(\d+)", s)]

def main():
    parser = argparse.ArgumentParser(description="Generate movie_manifest.json")
    parser.add_argument("--movies-dir", type=Path, default=DEFAULT_MOVIES_DIR)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    args = parser.parse_args()

    movies_dir = args.movies_dir
    out_dir = args.out_dir

    if not movies_dir.exists():
        print(f"ERROR: movies directory not found: {movies_dir}", file=sys.stderr)
        sys.exit(1)

    out_dir.mkdir(parents=True, exist_ok=True)

    # Pattern: <case>/<case>_<variable>_<axis>.mp4
    pattern = re.compile(r"^(.+?)_(.+?)_([xyz])\.mp4$")

    movies = []
    for mp4 in sorted(movies_dir.rglob("*.mp4"), key=lambda p: natural_key(str(p))):
        m = pattern.match(mp4.name)
        if not m:
            continue
        case, variable, axis = m.group(1), m.group(2), m.group(3)
        # Relative path from movies_dir root: <case>/<filename>
        rel = f"{case}/{mp4.name}"
        movies.append({"case": case, "variable": variable, "axis": axis, "path": rel})

    if not movies:
        print("WARNING: no MP4 files matched the expected pattern.", file=sys.stderr)

    # Derive sorted unique values for dropdowns
    cases     = sorted({m["case"]     for m in movies}, key=natural_key)
    variables = sorted({m["variable"] for m in movies}, key=natural_key)
    axes      = sorted({m["axis"]     for m in movies})

    manifest = {
        "cases": cases,
        "variables": variables,
        "axes": axes,
        "movies": movies,
    }

    out_path = out_dir / "movie_manifest.json"
    out_path.write_text(json.dumps(manifest, indent=2))
    print(f"Wrote {len(movies)} entries → {out_path}")
    print(f"  cases    : {cases}")
    print(f"  variables: {variables}")
    print(f"  axes     : {axes}")

if __name__ == "__main__":
    main()
