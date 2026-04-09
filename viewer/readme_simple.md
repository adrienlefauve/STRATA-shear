# Building a Web Viewer for Large Scientific Datasets

This is a brief description of a web-based visualization system built for DNS (Direct Numerical Simulation) data. The same approach works for any large 2D image or video data.

---

## Core idea

Two types of data to visualize:
- **2D snapshots** (large images, e.g. 32000×16000 px) — use deep-zoom tiling so the browser only loads what's visible
- **3D volume scans** (sequences of snapshots → MP4 movies) — use plain HTML5 video with custom playback controls

Both are served from static object storage (no server needed, no maintenance). The whole system is just HTML + JavaScript reading files from a URL.

---

## Architecture

```
HPC / compute cluster
    └── export slices → plot high resolution PNGs → tile into DZI pyramids
    └── plot low resolution volume-scan PNGs → encode MP4 movies

Object storage (R2 / S3 / any static host)
    ├── HTML viewers (3 pages: landing, slice viewer, volume viewer)
    ├── DZI tile pyramids  (deep-zoom tiles, JPEG, ~few GB)
    └── MP4 movies

Browser
    └── OpenSeadragon (deep-zoom pan & zoom, like Google Maps)
    └── HTML5 <video> with custom JS controls
```

---

## Key technologies

| Task | Tool | Notes |
| --- | --- | --- |
| Tiling large PNGs | [libvips](https://www.libvips.org/) + [pyvips](https://github.com/libvips/pyvips) | Very fast, handles images of any size |
| Deep-zoom viewer | [OpenSeadragon](https://openseadragon.github.io/) | Free, open source, plug-and-play |
| Object storage | Cloudflare R2 / AWS S3 / MinIO / any static host | R2 has no egress fees; S3 works identically |
| Transfer local→cloud | [rclone](https://rclone.org/) | Works with R2, S3, Dropbox, GCS, etc. |
| Video encoding | ffmpeg | Standard MP4 with H.264 |

---

## What to store where

```
your-bucket/
├── site/              ← the HTML pages (tiny, < 1 MB total)
├── tiles/             ← DZI pyramids from libvips (bulk of storage)
└── movies/            ← MP4 files
```

The HTML viewers contain a single `BASE_URL` constant pointing to the bucket. That's the only thing to configure.

---

## Data pipeline

1. **Export data** — extract 2D slices from your 3D fields (any format)
2. **Plot to PNG** — render each slice as a large PNG (matplotlib, ParaView, etc.)
3. **Tile the PNG** — `vips dzsave image.png output_dir` creates a DZI pyramid
4. **Write a manifest** — a JSON file listing all available cases/variables so the viewer knows what to show in its dropdowns
5. **Upload** — `rclone copy tiles/ remote:bucket/tiles/` (skips files already there)
6. **Open browser** — done

---

## Hosting options (instead of Cloudflare R2)

| Option | Cost | Notes |
| --- | --- | --- |
| Cloudflare R2 | Free up to 10 GB storage, no egress fees | Best for public data |
| AWS S3 | ~$0.023/GB/month + egress fees | Most widely supported |
| MinIO (self-hosted) | Free | Good if you have a lab server |
| GitHub Pages | Free, 1 GB limit | Only for the HTML files; tiles/movies need separate storage |
| University HPC web space | Often free | Check if HTTP range requests are supported (required for DZI) |

> **Important:** whatever host you use, it must support HTTP range requests (byte-range serving) for deep-zoom to work. All S3-compatible stores and nginx/Apache do. GitHub Pages does not serve range requests reliably.

## Using your own web server

Good news — almost none of the technology depends on the server. Here's the breakdown:

- **Tiling (libvips)** — runs entirely offline on your own machine or HPC. The server never touches it. You tile once, then just copy the resulting folder of JPEGs to the server.
- **Deep-zoom viewer (OpenSeadragon)** — just a JavaScript library loaded from a CDN. The server only needs to serve static files. Any web server (Apache, nginx) does this out of the box. The one requirement is HTTP range requests — Apache and nginx both support it by default, no config needed.
- **HTML5 video** — same story. Just MP4 files on disk, served statically. Range requests let the browser scrub without downloading the whole file.
- **The HTML pages themselves** — 3 plain `.html` files, no backend, no database, no PHP. Drop them anywhere.

So the full install on a university server would be:
1. Copy tiles + movies + HTML files to the web root
2. Edit one line in each HTML file: `BASE_URL = "https://their-server.edu/data/"`
3. Done — no software to install beyond what Apache already provides

> If videos won't scrub, add `Header set Accept-Ranges bytes` to `.htaccess`. This is rarely needed but fixes the issue if Apache is stripping range request headers.

---

## Prompts to get started with Copilot

A few prompts to give your own AI assistant to build this:

**Tiling script:**
> "Write a Python script using pyvips that takes a directory of PNG files and tiles each one into a DZI pyramid using `vips dzsave`. It should write a manifest JSON listing all the tiled images with their metadata (filename, width, height)."

**Viewer HTML:**
> "Write a single-page HTML file using OpenSeadragon 4.x that reads a manifest.json from a BASE_URL, populates a dropdown of available images, and loads the selected DZI tile pyramid. Add pan/zoom controls and a status bar."

**Movie viewer:**
> "Write a single-page HTML file with an HTML5 video player that reads a movie_manifest.json, populates dropdowns for case/variable/axis, and plays the selected MP4. Add a custom scrubber, playback speed selector, and loop toggle."

**rclone upload:**
> "Show me how to use rclone to upload a directory of files to a Cloudflare R2 bucket, skipping files that are already there, using 16 parallel transfers."
