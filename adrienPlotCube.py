#!/usr/bin/env python3

# EXAMPLE CALL python adrienPlotCube.py --case R1P1 --var r --stride 1 --ix 400 --top-frac 0.8 --width 2000 --cbar
import argparse
from pathlib import Path

import numpy as np
import plotly.graph_objects as go

import adrienParamClassSheared as param

VARCFG = {
    # var : (plotly_colorscale, cmin, cmax, colorbar_title)
    "u": ("RdBu",   -5,   5,  "u/√Ek"),
    "v": ("RdBu",   -5,   5,  "v/√Ek"),
    "w": ("RdBu",   -5,   5,  "w/√Ek"),
    "b": ("Viridis",-5,   5,  "b/√(N²Ep)"),
    "e": ("Magma",  -2,   2,  "log₁₀(ε/⟨ε⟩)"),
    "c": ("Hot",    -2,   3,  "log₁₀(χ/⟨χ⟩)"),
    "r": ("Viridis", -5e-4, 5e-4, "r"),
}


def load_binary(var_name, p, dtype="single", order="F", chop_x_pad=2):
    file_path = Path(p.dirPath) / f"{var_name}_{p.tStamp}"
    X = np.memmap(
        str(file_path),
        dtype=dtype,
        mode="r",
        shape=(p.Nx + chop_x_pad, p.Ny, p.Nz),
        order=order,
    )
    return X[:-chop_x_pad, :, :]

def plot_one_frame(
    cube, x, y, z,
    xSt, top_frac,
    cmin, cmax, colorscale, ctitle,
    add_colorbar=True,
    width=2500, height=1406,
):
    X, Y, Z = np.meshgrid(x, y, z, indexing="ij")

    top_frac = min(max(top_frac, 0.0), 1.0)
    topIdx = int(round(top_frac * (len(z) - 1)))

    y_idx = 1 if cube.shape[1] > 1 else 0

    fig = go.Figure()

    # Top face (only trace that shows the colorbar)
    fig.add_trace(go.Surface(
        x=X[xSt:, :, topIdx], y=Y[xSt:, :, topIdx], z=Z[xSt:, :, topIdx],
        surfacecolor=cube[:, :, topIdx][xSt:, :],
        colorscale=colorscale, cmin=cmin, cmax=cmax,
        showscale=add_colorbar,
        colorbar=dict(
            title=ctitle,
            len=0.7,
            thickness=24,
            x=1.02,   # push outside so it doesn't shrink the scene
        ) if add_colorbar else None,
    ))

    # Left/front face at x = xSt
    fig.add_trace(go.Surface(
        x=X[xSt, :, :topIdx+1], y=Y[xSt, :, :topIdx+1], z=Z[xSt, :, :topIdx+1],
        surfacecolor=cube[xSt, :, :topIdx+1],
        colorscale=colorscale, cmin=cmin, cmax=cmax,
        showscale=False
    ))

    # Front vertical face at y = y_idx (Miles-style)
    fig.add_trace(go.Surface(
        x=X[xSt:, y_idx, :topIdx+1], y=Y[xSt:, y_idx, :topIdx+1], z=Z[xSt:, y_idx, :topIdx+1],
        surfacecolor=cube[:, y_idx, :topIdx+1][xSt:, :],
        colorscale=colorscale, cmin=cmin, cmax=cmax,
        showscale=False
    ))

    # --- box edges (Miles-style) ---
    x0, x1 = x[0], x[-1]
    y0, y1 = y[0], y[-1]
    z0, z1 = z[0], z[-1]
    lines = [
        # Bottom face
        ([x0, x1], [y0, y0], [z0, z0]),
        ([x1, x1], [y0, y0], [z0, z1]),
        ([x1, x0], [y0, y0], [z1, z1]),
        ([x0, x0], [y0, y0], [z1, z0]),
        # Top face
        ([x0, x1], [y1, y1], [z0, z0]),
        ([x1, x1], [y1, y1], [z0, z1]),
        ([x1, x0], [y1, y1], [z1, z1]),
        ([x0, x0], [y1, y1], [z1, z0]),
        # Vertical edges
        ([x0, x0], [y0, y1], [z0, z0]),
        ([x1, x1], [y0, y1], [z0, z0]),
        ([x1, x1], [y0, y1], [z1, z1]),
        ([x0, x0], [y0, y1], [z1, z1]),
    ]
    
    for xi, yi, zi in lines:
        fig.add_trace(go.Scatter3d(
            x=xi, y=yi, z=zi,
            mode="lines",
            line=dict(color="black", width=6),
            showlegend=False
        ))

    fig.update_layout(
        autosize=False,
        width=width,
        height=height,
        margin=dict(l=0, r=0, b=0, t=0),
        scene=dict(
            domain=dict(x=[0, 1], y=[0, 1]),
            aspectmode="manual",
            aspectratio=dict(x=1, y=1/2, z=1/4),
            xaxis=dict(visible=False, showspikes=False, range=[x0, x1]),
            yaxis=dict(visible=False, showspikes=False, range=[y0, y1]),
            zaxis=dict(visible=False, showspikes=False, range=[z0, z1]),
            camera=dict(
                eye=dict(x=-0.7, y=-0.7, z=0.5),
                center=dict(x=-0.08, y=0, z=-0.12),
            ),
        ),
    )

    return fig

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--case", required=True)
    ap.add_argument("--var", default="r")
    ap.add_argument("--stride", type=int, default=30, help="Downsample stride in x,y,z")
    ap.add_argument("--ix", type=int, required=True, help="x index in the ORIGINAL volume (0..Nx-1)")
    ap.add_argument("--top-frac", type=float, default=0.7)
    ap.add_argument("--outdir", default="figures/3D/")
    ap.add_argument("--width", type=int, default=2000)
    ap.add_argument("--scale", type=float, default=1.0)
    ap.add_argument("--var-scale", type=float, default=1.0)
    ap.add_argument("--cbar", action="store_true", help="show colorbar")
    args = ap.parse_args()

    p = param.generate()[args.case]

    if args.var not in VARCFG:
        raise ValueError(f"--var {args.var} not in VARCFG. Add it there.")
    colorscale, cmin, cmax, ctitle = VARCFG[args.var]

    if args.stride < 1:
        raise ValueError("--stride must be >= 1")

    if args.ix < 0 or args.ix > p.Nx - 1:
        raise ValueError(f"--ix must be in [0, {p.Nx - 1}] (original volume). Got {args.ix}")

    data = load_binary(args.var, p)
    cube = (data[::args.stride, ::args.stride, ::args.stride]) / args.var_scale
    Nx_ds, Ny_ds, Nz_ds = cube.shape

    # Map original x-index -> downsampled x-index
    xSt = args.ix // args.stride
    xSt = max(0, min(xSt, Nx_ds - 1))

    # Miles-style aspect coordinates
    x = np.linspace(0, 1.0, Nx_ds)
    y = np.linspace(0, 0.5, Ny_ds)
    z = np.linspace(0, 0.25, Nz_ds)

    height = int(args.width * 0.7)  # * 9 / 16

    fig = plot_one_frame(
        cube, x, y, z,
        xSt=xSt, top_frac=args.top_frac,
        cmin=cmin, cmax=cmax,
        colorscale=colorscale, ctitle=ctitle,
        add_colorbar=args.cbar,
        width=args.width, height=height,
    )

    outdir = Path(args.outdir) / args.case
    outdir.mkdir(parents=True, exist_ok=True)

    outpng = outdir / f"{args.case}_{args.var}_ix{args.ix:06d}.png"
    outpng.unlink(missing_ok=True)

    fig.write_image(
        str(outpng),
        width=args.width,
        height=height,
        scale=args.scale,
    )


if __name__ == "__main__":
    main()