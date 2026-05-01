# STRATA Mean-Shear Viewer — Offline edition

This folder contains a self-contained interactive viewer for the STRATA
direct-numerical-simulation dataset. No internet connection is required;
everything runs locally in your browser.

## How to launch

### macOS

Double-click **`start-viewer.command`**. A Terminal window will open,
a local web server starts, and your default browser opens automatically
at `http://localhost:8000/`. Close the Terminal window when you're done.

If macOS warns "cannot be opened because it is from an unidentified developer",
right-click `start-viewer.command` → **Open** → **Open**. (One-time approval.)

### Linux / Windows (with Python installed)

Open a terminal in this folder and run:

```bash
python3 -m http.server 8000
```

Then open `http://localhost:8000/` in your browser.

## What's inside

```
STRATA-viewer/
├── README.md                 ← this file
├── start-viewer.command      ← macOS launcher (double-click)
├── index.html                ← landing page
├── slice_viewer/
│   ├── index.html            ← OpenSeadragon DZI viewer
│   └── slice_manifest.json
├── movie_viewer/
│   ├── index.html            ← HTML5 video viewer
│   └── movie_manifest.json
├── viewer/                   ← Deep Zoom Image tile pyramids
│   └── <case>/
│       └── <var>_<axis><idx>.dzi   (+ tile pyramid in <var>_<axis><idx>_files/)
└── volumes/                  ← MP4 cube-scan movies
    └── <case>/
        └── <case>_<var>_<axis>.mp4
```

The 13 simulation cases are: `R1P1, R1P7, R1P50, R4P1, R4P7, R4P50,
R6P1, R6P7, R6P50, R8P1, R8P7, R10P1, R10P7`.
Variables: `u, v, w, r` (density), `ee` ($\varepsilon$, TKE dissipation),
`chi` ($\chi$, scalar dissipation).

## Why a local web server?

Modern browsers block JavaScript from reading sibling files when the page is
opened via `file://` (cross-origin policy). The viewer needs to fetch the DZI
tile manifests and individual tiles, so a local web server is the simplest
way to make those reads work. The launcher script above does this for you.

## Troubleshooting

- **"Address already in use"**: another program is on port 8000. The
  launcher will try 8001, 8002, … automatically. If you ran `python3 -m
  http.server` manually, pick a different port.
- **Tiles or movies don't load**: confirm the `viewer/` and `volumes/`
  folders are alongside `index.html` (i.e. were extracted from the zip
  intact, not nested inside another folder). The viewer expects the
  layout shown above.
- **Browser asks to download `.dzi` instead of opening it**: that's
  expected — `.dzi` files are loaded by the JavaScript on the page,
  not opened directly. Make sure you're viewing via
  `http://localhost:8000/`, not by double-clicking an HTML file.

## Companion materials

- Code (post-processing pipeline that produced these tiles + movies):
  https://github.com/adrienlefauve/strata-shear
- Companion paper: Lefauve et al., *SHASSST*, 2026.
- Constellation deposit (raw binaries, NetCDFs, source figures):
  *(link in the deposit README)*
