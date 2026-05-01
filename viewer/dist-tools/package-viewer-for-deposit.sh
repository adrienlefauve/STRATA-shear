#!/bin/bash
# package-viewer-for-deposit.sh
# Build a self-contained, offline-ready viewer zip from local sources.
#
# Inputs (override via environment variables before running):
#   VIEWER_SRC   — strata-shear/viewer/ in this repo                (default: ../)
#   TILES_SRC    — directory of DZI tile pyramids (per-case)        (no default; required)
#   MOVIES_SRC   — directory of MP4 cube movies (per-case)          (no default; required)
#   OUT_DIR      — where to write the zip                           (default: $HOME/Desktop)
#
# Output:
#   $OUT_DIR/STRATA-viewer.zip   — drop into Constellation deposit

set -e
HERE="$(cd "$(dirname "$0")" && pwd)"
VIEWER_SRC="${VIEWER_SRC:-$(cd "$HERE/.." && pwd)}"
OUT_DIR="${OUT_DIR:-$HOME/Desktop}"
WORK_DIR="$(mktemp -d)"
DEPOSIT="$WORK_DIR/STRATA-viewer"

if [ -z "${TILES_SRC:-}" ] || [ ! -d "$TILES_SRC" ]; then
  echo "ERROR: TILES_SRC not set or not a directory."
  echo ""
  echo "Run like:"
  echo "  TILES_SRC='/Volumes/MediaDrive1/.../tiles' \\"
  echo "  MOVIES_SRC='/Volumes/MediaDrive1/.../cube-movies' \\"
  echo "  ./package-viewer-for-deposit.sh"
  exit 1
fi
if [ -z "${MOVIES_SRC:-}" ] || [ ! -d "$MOVIES_SRC" ]; then
  echo "ERROR: MOVIES_SRC not set or not a directory."
  exit 1
fi

echo "→ Source viewer code:  $VIEWER_SRC"
echo "→ Source tiles:        $TILES_SRC"
echo "→ Source movies:       $MOVIES_SRC"
echo "→ Building in:         $DEPOSIT"
echo ""

# 1. Skeleton
mkdir -p "$DEPOSIT"/{slice_viewer,movie_viewer,viewer,volumes,dist-tools}

# 2. HTML + manifests
cp "$VIEWER_SRC/landing/index.html"                     "$DEPOSIT/index.html"
cp "$VIEWER_SRC/slice_viewer/index.html"                "$DEPOSIT/slice_viewer/"
cp "$VIEWER_SRC/slice_viewer/slice_manifest.json"       "$DEPOSIT/slice_viewer/"
cp "$VIEWER_SRC/movie_viewer/index.html"                "$DEPOSIT/movie_viewer/"
cp "$VIEWER_SRC/movie_viewer/movie_manifest.json"       "$DEPOSIT/movie_viewer/"

# 3. Launcher + offline README
cp "$VIEWER_SRC/dist-tools/start-viewer.command"        "$DEPOSIT/start-viewer.command"
chmod +x "$DEPOSIT/start-viewer.command"
cp "$VIEWER_SRC/dist-tools/OFFLINE_README.md"           "$DEPOSIT/README.md"

# 4. Background image, if present in source
[ -f "$VIEWER_SRC/landing/bg.jpg" ] && cp "$VIEWER_SRC/landing/bg.jpg" "$DEPOSIT/bg.jpg" || true

# 5. Heavy data — copy tiles and movies
echo "→ Copying tiles (this may take a while)..."
rsync -a --info=progress2 "$TILES_SRC/" "$DEPOSIT/viewer/"
echo "→ Copying movies..."
rsync -a --info=progress2 "$MOVIES_SRC/" "$DEPOSIT/volumes/"

# 6. Total size before zip
echo ""
echo "→ Deposit folder size:"
du -sh "$DEPOSIT"
echo ""

# 7. Zip it
mkdir -p "$OUT_DIR"
ZIP_PATH="$OUT_DIR/STRATA-viewer.zip"
rm -f "$ZIP_PATH"
echo "→ Zipping → $ZIP_PATH (uncompressed; tiles are already JPG/MP4)"
( cd "$WORK_DIR" && zip -r -0 -q "$ZIP_PATH" "STRATA-viewer" )

ls -lh "$ZIP_PATH"
echo ""
echo "✓ Done. Drop $ZIP_PATH into the Constellation deposit."
echo ""
echo "Cleaning up scratch dir: $WORK_DIR"
rm -rf "$WORK_DIR"
