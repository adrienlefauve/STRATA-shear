
# DNS Viewer: Project Summary

### What was built
A complete web-based interactive visualization system for Direct Numerical Simulation (DNS) data, publicly accessible from anywhere via a single URL.

---

### Architecture

| Component | Technology | Purpose |
| --- | --- | --- |
| Object storage | Cloudflare R2 | Hosts all heavy data (tiles, movies) and the HTML site |
| Tile generation | libvips + Python | Converts large PNGs into Deep Zoom Image (DZI) pyramids |
| Slice viewer | OpenSeadragon | Google Maps-style pan & zoom for 2D snapshots |
| Volume viewer | HTML5 `<video>` + custom JS | Streams and plays MP4 cube movies with playback controls |
| Landing page | Plain HTML/CSS | Branded entry point with background image |

---

### Data pipeline
1. **HPC (SLURM)** — `export_slices.py` exports NetCDF slices from binary 3D fields
2. **`plot_slices.py`** — renders NetCDF slices to large PNGs (one per variable/scan position)
3. **`tile_images.py`** — tiles PNGs into DZI pyramids (libvips `dzsave`)
4. **`gen_slice_manifest.py`** — scans tile output, writes `slice_manifest.json`
5. **`gen_movie_manifest.py`** — scans MP4 cube movies, writes `movie_manifest.json`
5. **rclone** — uploads tiles → `r2:.../viewer/`, movies → `r2:.../volumes/`, HTML → `r2:.../site/`

---

### Public URLs
- **Landing page:** `https://pub-ae06ec6e266444d2a93dba965f4447b2.r2.dev/site/index.html`
- **Slice Viewer:** `.../site/slice_viewer/index.html`
- **Volume Viewer:** `.../site/movie_viewer/index.html`

---

### Key files (local)
```
adrien/
├── export_slices.py              # HPC: NetCDF → binary slices
├── plot_slices.py                # NetCDF → PNG snapshots
└── viewer/
    ├── tile_images.py            # PNG → DZI tiles (libvips)
    ├── gen_slice_manifest.py     # Scan tiles → slice_manifest.json
    ├── gen_movie_manifest.py     # Scan MP4s → movie_manifest.json
    ├── landing/index.html        # STRATA landing page
    ├── slice_viewer/index.html   # DNS Slice Viewer (OpenSeadragon)
    └── movie_viewer/index.html   # DNS Volume Viewer (HTML5 video)
```

---

### Cases / data
- **13 cases:** R1P1, R1P7, R1P50, R4P1, R4P7, R4P50, R6P1, R6P7, R6P50, R8P1, R8P7, R10P1, R10P7
- **Variables:** u, v, w, r, ε (ee), χ (chi)
- **234 movies** (x/y/z scans per variable per case)
- **Slice tiles:** ~4 GB, still uploading at time of writing






## Step-by-step setup guide

### One-time setup (already done)

**1. Install dependencies (local Mac)**
```sh
brew install vips
pip install pyvips
brew install rclone
```

**2. Configure rclone for Cloudflare R2**
```sh
rclone config
# → New remote, name: r2
# → Type: S3-compatible
# → Enter Access Key ID and Secret Key from Cloudflare R2 dashboard
# → Endpoint: https://<account-id>.r2.cloudflarestorage.com
# → Leave region blank, no advanced config
```

**3. Create R2 bucket**
- Cloudflare dashboard → R2 → Create bucket: `strata-dns-snapshots`
- Settings → Public access → Allow (enable r2.dev public URL)

**4. Generate tiles from PNGs**
```sh
cd /path/to/strata-shear/viewer   # adjust to where you cloned the repo
python tile_images.py --skip-existing
```

**5. Generate manifests**
```sh
python gen_slice_manifest.py
python gen_movie_manifest.py
```

**6. Assemble deploy folder**
```sh
mkdir -p /tmp/dns-deploy/slice_viewer /tmp/dns-deploy/movie_viewer
cp viewer/landing/index.html /tmp/dns-deploy/
cp viewer/slice_viewer/index.html /tmp/dns-deploy/slice_viewer/
cp viewer/slice_viewer/slice_manifest.json /tmp/dns-deploy/slice_viewer/
cp viewer/movie_viewer/index.html /tmp/dns-deploy/movie_viewer/
cp viewer/movie_viewer/movie_manifest.json /tmp/dns-deploy/movie_viewer/
cp /path/to/bg.jpg /tmp/dns-deploy/
```

**7. Upload everything to R2**
```sh
# Tiles (large, ~4GB)
rclone copy viewer/slice_viewer/tiles r2:strata-dns-snapshots/viewer --progress

# Movies
rclone copy /path/to/cube-movies r2:strata-dns-snapshots/volumes --progress

# HTML site
rclone copy /tmp/dns-deploy r2:strata-dns-snapshots/site --ignore-times --progress
```

---

### How to update later

**New/updated movies:**
```sh
# Re-run manifest generator first
python gen_movie_manifest.py
cp viewer/movie_viewer/movie_manifest.json /tmp/dns-deploy/movie_viewer/

# Upload only new/changed movies (rclone skips existing unchanged files)
rclone copy /path/to/cube-movies r2:strata-dns-snapshots/volumes --progress

# Re-deploy updated manifest
rclone copy /tmp/dns-deploy/movie_viewer r2:strata-dns-snapshots/site/movie_viewer --ignore-times --progress
```

**New/updated slice images:**
```sh
# Re-tile only new PNGs
python tile_images.py --skip-existing

# Re-generate manifest
python gen_slice_manifest.py
cp viewer/slice_viewer/slice_manifest.json /tmp/dns-deploy/slice_viewer/

# Upload only new tiles (rclone skips existing)
rclone copy viewer/slice_viewer/tiles r2:strata-dns-snapshots/viewer --progress

# Re-deploy manifest
rclone copy /tmp/dns-deploy/slice_viewer r2:strata-dns-snapshots/site/slice_viewer --ignore-times --progress
```

**Update the HTML viewers (UI changes):**
```sh
cp viewer/slice_viewer/index.html /tmp/dns-deploy/slice_viewer/
cp viewer/movie_viewer/index.html /tmp/dns-deploy/movie_viewer/
rclone copy /tmp/dns-deploy/slice_viewer/index.html r2:strata-dns-snapshots/site/slice_viewer --ignore-times
rclone copy /tmp/dns-deploy/movie_viewer/index.html r2:strata-dns-snapshots/site/movie_viewer --ignore-times
```

**Key principle:** rclone always skips files that haven't changed, so re-running any upload command is safe and efficient.

---

### Note: the facility can be tested locally (no Cloudflare) before deployment on a cloud

The HTML viewers have `BASE_URL` hardcoded to the R2 public URL. To test locally, you need to:
1. Mirror the R2 structure in a single folder
2. Patch `BASE_URL` to `http://localhost:8000`
3. Serve it with Python's built-in HTTP server

**Set up the local mirror:**
```sh
LOCAL=/tmp/dns-local
mkdir -p $LOCAL/viewer $LOCAL/volumes $LOCAL/slice_viewer $LOCAL/movie_viewer

# HTML + manifests
cp viewer/landing/index.html       $LOCAL/index.html
cp viewer/slice_viewer/index.html  $LOCAL/slice_viewer/index.html
cp viewer/slice_viewer/slice_manifest.json $LOCAL/slice_viewer/
cp viewer/movie_viewer/index.html  $LOCAL/movie_viewer/index.html
cp viewer/movie_viewer/movie_manifest.json $LOCAL/movie_viewer/
cp /path/to/bg.jpg                 $LOCAL/

# Tiles and movies (can be slow — symlink instead if on same disk)
ln -s /path/to/tiles   $LOCAL/viewer      # or: cp -r ...
ln -s /path/to/movies  $LOCAL/volumes     # or: cp -r ...
```

**Patch BASE_URL to localhost:**
```sh
sed -i '' 's|https://pub-ae06ec6e266444d2a93dba965f4447b2.r2.dev/viewer|http://localhost:8000/viewer|g' $LOCAL/slice_viewer/index.html
sed -i '' 's|https://pub-ae06ec6e266444d2a93dba965f4447b2.r2.dev/volumes|http://localhost:8000/volumes|g' $LOCAL/movie_viewer/index.html
```

**Serve and open:**
```sh
cd $LOCAL
python -m http.server 8000
# Then open: http://localhost:8000/index.html
```

> Note: browsers block some local file access — always use `http.server`, not `file://` URLs. The patched copies in `/tmp/dns-local/` are throwaway; the originals in `adrien/viewer/` are unchanged.

---


## Things to remember

### Cloudflare R2 bucket structure
```
strata-dns-snapshots/
├── site/                      ← HTML viewers + assets
│   ├── index.html             ← landing page
│   ├── bg.jpg                 ← background image
│   ├── slice_viewer/
│   │   ├── index.html
│   │   └── slice_manifest.json
│   └── movie_viewer/
│       ├── index.html
│       └── movie_manifest.json
├── viewer/                    ← DZI tile pyramids (slice tiles)
│   └── <case>/
│       └── <vargroup>_<axis><idx>_files/
│           └── <zoom_level>/  ← tile JPEGs
└── volumes/                   ← MP4 cube movies
    └── <case>/
        └── <case>_<var>_<axis>.mp4
```
Example tile path: `viewer/R1P1/all_variables_x768_files/12/3_4.jpg`  
Example movie path: `volumes/R1P1/R1P1_chi_x.mp4`

### BASE_URL values (already set in HTML files)
- Slice viewer: `https://pub-ae06ec6e266444d2a93dba965f4447b2.r2.dev/viewer`
- Volume viewer: `https://pub-ae06ec6e266444d2a93dba965f4447b2.r2.dev/volumes`

### R2 API credentials location
```
~/.config/rclone/rclone.conf   ← rclone config with R2 keys
```

### Gotchas encountered
- R2 public URL is `pub-xxx.r2.dev` — the S3 endpoint `<account>.r2.cloudflarestorage.com` is **not** public
- API token needs **Read + Write** for uploads; public access is set separately on the bucket
- rclone `copy` won't re-upload unchanged files; use `--ignore-times` to force
- `rclone lsd r2:` fails (ListBuckets denied) but `rclone ls r2:bucketname` works fine
- The `movies` symlink in `movie_viewer/` is local only — not uploaded to R2
- When deploying HTML changes, always `cp` to dns-deploy first, then rclone

### If you need to re-tile (e.g. new cases on HPC)
1. Run `plot_slices.py` on HPC to generate new PNGs
2. Copy PNGs locally
3. Run `python tile_images.py --skip-existing` then `python gen_slice_manifest.py`
4. Upload new tiles with rclone (safe to re-run, skips existing)
5. Regenerate and re-upload `slice_manifest.json`

### Speeding up rclone for large uploads
```sh
rclone copy ... --transfers=16 --progress
```
