# utils.py
import numpy as np
import os
from mpl_toolkits.axes_grid1 import make_axes_locatable
import psutil
from pathlib import Path
from datetime import datetime
import matplotlib.pyplot as plt
from matplotlib import cm, colors
from typing import Tuple
from scipy.io import netcdf_file
from PIL import Image
from dataclasses import dataclass
from typing import Dict, Tuple, Optional, Iterable, Union, List

# ---------------------------------------------------------------------
# load_binary
# ---------------------------------------------------------------------
# Purpose:
#   Low-level reader for raw DNS binary output written by the solver.
#
# What it does:
#   - Memory-maps a single variable (u, v, w, r, etc.) from disk
#   - Assumes Fortran-order float32 array with shape (Nx+2, Ny, Nz)
#   - Drops the last two padded x-rows used internally by the solver
#
# Why it exists:
#   This mirrors the solver’s exact output format and avoids loading
#   the full array into memory. All higher-level routines ultimately
#   rely on this convention, either directly or via LazyField.
#
# Used by:
#   - compute_eps
#   - compute_chi
#   - LazyField (conceptually identical layout)
def load_binary(varName, p):
    filePath = p.dirPath + varName + "_" + p.tStamp
    X = np.memmap(filePath, dtype="single", mode="r",
                  shape=(p.Nx+2, p.Ny, p.Nz), order="F")
    return X[:-2, :, :]  # chop off two rows of zeros, which SdbK puts there to orient ourselves

# ---------------------------------------------------------------------
# d_periodic_4th
# ---------------------------------------------------------------------
# Purpose:
#   Compute a 4th-order accurate periodic finite-difference derivative.
#
# What it does:
#   - Uses periodic wrap-around via np.roll
#   - Applies standard 4th-order central stencil
#
# Why it exists:
#   Needed for accurate gradients (velocity, buoyancy) when computing
#   dissipation (ε) and scalar variance dissipation (χ).
#
# Used by:
#   - compute_eps
#   - compute_chi
def d_periodic_4th(f, dx, axis):
    return (
        -np.roll(f, -2, axis=axis)
        + 8*np.roll(f, -1, axis=axis)
        - 8*np.roll(f,  1, axis=axis)
        + np.roll(f,  2, axis=axis)
    ) / (12.0 * dx)

# ---------------------------------------------------------------------
# compute_chi
# ---------------------------------------------------------------------
# Purpose:
#   Compute scalar dissipation rate χ from buoyancy gradients. 
#   Obsolete now that Steve provides us with it computed spectrally
#
# What it does:
#   - Loads density r if buoyancy b is not provided
#   - Computes ∇b using 4th-order derivatives
#   - Applies χ = (D / N²) |∇b|²
#
# Why it exists:
#   χ is not always stored explicitly in the DNS output but is required
#   for diagnostics and plotting alongside ε.
#
# Used by:
#   - Preprocessing steps before plotting
#   - Validation of DNS statistics
def compute_chi(p,b=None):
    dx = p.Lx / p.Nx
    dy = p.Ly / p.Ny
    dz = p.Lz / p.Nz

    if b is None:
        r = load_binary("r", p)
        b = -p.zAccel * r

    bx = d_periodic_4th(b, dx, axis=0)
    by = d_periodic_4th(b, dy, axis=1)
    bz = d_periodic_4th(b, dz, axis=2)

    D = p.kinV / p.Pr
    N2 = -p.dGrad * p.zAccel
    chi = (D / N2) * (bx**2 + by**2 + bz**2)
    return chi


# def compute_eps(p):
#     dx = p.Lx / p.Nx
#     dy = p.Ly / p.Ny
#     dz = p.Lz / p.Nz
#     u = load_binary("u", p); bar.update(1);bar.refresh();
#     v = load_binary("v", p); bar.update(1);bar.refresh(); 
#     w = load_binary("w", p); bar.update(1);bar.refresh()
#     ux = d_periodic_4th(u, dx, axis=0); 
#     uy = d_periodic_4th(u, dy, axis=1); uz = d_periodic_4th(u, dz, axis=2); 
#     vx = d_periodic_4th(v, dx, axis=0); vy = d_periodic_4th(v, dy, axis=1); vz = d_periodic_4th(v, dz, axis=2); 
#     wx = d_periodic_4th(w, dx, axis=0); wy = d_periodic_4th(w, dy, axis=1); wz = d_periodic_4th(w, dz, axis=2); 
    
#     nu = p.kinV
#     eps = nu * (2*ux**2 + 2*vy**2 + 2*wz**2 + (uy + vx)**2 + (uz + wx)**2 + (vz + wy)**2)
#     return eps

# ---------------------------------------------------------------------
# compute_eps
# ---------------------------------------------------------------------
# Purpose:
#   Compute kinetic energy dissipation rate ε from velocity gradients.
#   Obsolete now that Steve provides us with it computed spectrally
#
# What it does:
#   - Loads u, v, w if not provided
#   - Computes all velocity gradients with 4th-order accuracy
#   - Applies the full strain-rate tensor contraction
#
# Why it exists:
#   ε is a fundamental turbulence diagnostic and is required for
#   normalisation, log-scaling, and comparison with χ.
#
# Used by:
#   - Preprocessing pipelines
#   - Statistical summaries
def compute_eps(p, u=None, v=None, w=None):
    dx = p.Lx / p.Nx
    dy = p.Ly / p.Ny
    dz = p.Lz / p.Nz

    if u is None:
        u = load_binary("u", p)
    if v is None:
        v = load_binary("v", p)
    if w is None:
        w = load_binary("w", p)

    ux = d_periodic_4th(u, dx, axis=0); uy = d_periodic_4th(u, dy, axis=1); uz = d_periodic_4th(u, dz, axis=2)
    vx = d_periodic_4th(v, dx, axis=0); vy = d_periodic_4th(v, dy, axis=1); vz = d_periodic_4th(v, dz, axis=2)
    wx = d_periodic_4th(w, dx, axis=0); wy = d_periodic_4th(w, dy, axis=1); wz = d_periodic_4th(w, dz, axis=2)

    nu = p.kinV
    eps = nu * (2*ux**2 + 2*vy**2 + 2*wz**2 + (uy + vx)**2 + (uz + wx)**2 + (vz + wy)**2)

    return eps

# def compute_eps_pseudo(p):
#     dx = p.Lx / p.Nx
#     dy = p.Ly / p.Ny
#     dz = p.Lz / p.Nz

#     u = load_binary("u", p)
#     v = load_binary("v", p)
#     w = load_binary("w", p)

#     ux = d_periodic_4th(u, dx, axis=0); uy = d_periodic_4th(u, dy, axis=1); uz = d_periodic_4th(u, dz, axis=2)
#     vx = d_periodic_4th(v, dx, axis=0); vy = d_periodic_4th(v, dy, axis=1); vz = d_periodic_4th(v, dz, axis=2)
#     wx = d_periodic_4th(w, dx, axis=0); wy = d_periodic_4th(w, dy, axis=1); wz = d_periodic_4th(w, dz, axis=2)

#     nu = p.kinV
#     eps_pseudo = nu * (ux**2 + uy**2 + uz**2 + vx**2 + vy**2 + vz**2 + wx**2 + wy**2 + wz**2)
#     return eps_pseudo

# ---------------------------------------------------------------------
# imshow_with_cbar
# ---------------------------------------------------------------------
# Purpose:
#   Standardised imshow + colorbar layout for all slice plots.
#
# What it does:
#   - Plots Z.T with origin="lower"
#   - Attaches a compact colorbar on the right
#   - Forces symmetric tick placement when appropriate
#
# Why it exists:
#   Ensures visual consistency across all notebooks and figures.
#
# Used by:
#   - plot_slices_all_vars
#   - plot_slices_derived_bundle
def imshow_with_cbar(ax, Z, cmap, vmin, vmax, cbar_label):
    im = ax.imshow(
        Z.T,
        origin="lower",
        cmap=cmap,
        vmin=vmin,
        vmax=vmax,
        aspect="equal",
    )

    divider = make_axes_locatable(ax)
    cax = divider.append_axes("right", size="3.5%", pad=0.08)
    cb = ax.figure.colorbar(im, cax=cax)

    # Force endpoints + midpoint
    cb.set_ticks([vmin, 0, vmax])

    cb.set_label(cbar_label)

    return im, cb

# ---------------------------------------------------------------------
# set_index_axis
# ---------------------------------------------------------------------
# Purpose:
#   Clean axis tick labelling for very large grids.
#
# What it does:
#   - Places ticks every `step`
#   - Labels only every `label_step`
#
# Why it exists:
#   Prevents unreadable axes when Nx, Ny, Nz are O(10^4).
#
# Used by:
#   - All slice plotting routines
def set_index_axis(ax, axis="x", N=1, label=None, step=500, label_step=1000):
    """
    Ticks every `step`, labels only every `label_step`.

    Example (N=3200):
      ticks: 0,500,1000,1500,2000,2500,3000
      labels: 0,'' ,1000,'' ,2000,'' ,3000
    """
    N = int(N)

    ticks = list(range(0, N, step))

    labels = []
    for t in ticks:
        if t % label_step == 0:
            labels.append(str(t))
        else:
            labels.append("")

    if axis == "x":
        ax.set_xticks(ticks)
        ax.set_xticklabels(labels)
        if label is not None:
            ax.set_xlabel(label)
    elif axis == "y":
        ax.set_yticks(ticks)
        ax.set_yticklabels(labels)
        if label is not None:
            ax.set_ylabel(label)
    else:
        raise ValueError("axis must be 'x' or 'y'")
        
# ---------------------------------------------------------------------
# memory_report
# ---------------------------------------------------------------------
# Purpose:
#   Inspect current notebook memory usage.
#
# What it does:
#   - Lists large NumPy arrays in scope
#   - Reports RSS, cgroup limits, and remaining headroom
#
# Why it exists:
#   Critical when working near memory limits on Frontier / OLCF nodes.
#
# Used by:
#   - Interactive debugging
#   - Sanity checks after loading slices
def memory_report(globals_dict=None, min_gb=0.05):
    if globals_dict is None:
        globals_dict = globals()

    rows = []
    for name, obj in globals_dict.items():
        if isinstance(obj, np.ndarray):
            size_gb = obj.nbytes / 1024**3
            if size_gb >= min_gb:
                rows.append((name, size_gb, obj.shape, obj.dtype))
    rows.sort(key=lambda x: x[1], reverse=True)

    if rows:
        for name, size_gb, shape, dtype in rows:
            print(f"{name:25s} {size_gb:6.2f} GB  shape={shape}  dtype={dtype}")
    else:
        print("(No NumPy arrays above threshold)")

    process = psutil.Process(os.getpid())
    used_gb = process.memory_info().rss / 1024**3
    vm = psutil.virtual_memory()
    node_total_gb = vm.total / 1024**3

    def _cgroup_limit_gb():
        paths = ["/sys/fs/cgroup/memory.max", "/sys/fs/cgroup/memory/memory.limit_in_bytes"]
        for pth in paths:
            if os.path.exists(pth):
                with open(pth) as f:
                    val = f.read().strip()
                if val.isdigit():
                    return int(val) / 1024**3
        return None

    limit_gb = _cgroup_limit_gb()
    if limit_gb:
        percent_used = 100 * used_gb / limit_gb
        avail_to_me_gb = max(limit_gb - used_gb, 0)
        percent_left = 100 * avail_to_me_gb / limit_gb
        print()
        print(f"{'Notebook memory used':25s}: {used_gb:6.2f} GB ({percent_used:5.1f} %)")
        print(f"{'Remaining available to me':25s}: {avail_to_me_gb:6.2f} GB ({percent_left:5.1f} %)")
        print(f"{'Container memory limit':25s}: {limit_gb:6.2f} GB")
    else:
        print()
        print(f"{'Notebook memory used':25s}: {used_gb:6.2f} GB")
        print("(No cgroup limit detected)")
    print(f"{'Total node memory':25s}: {node_total_gb:6.2f} GB")

# ---------------------------------------------------------------------
# save_slice_figure
# ---------------------------------------------------------------------
# Purpose:
#   Save multi-panel slice figures with a consistent naming scheme.
#
# What it does:
#   - Embeds case name, slice direction, index, and timestamp
#
# Why it exists:
#   Ensures figures are uniquely identifiable and reproducible.
#
# Used by:
#   - plot_slices_all_vars
#   - plot_slices_derived_bundle
def save_slice_figure(fig, p, slice_dir, idx, outdir="figures", fmt="png", dpi=300):
    Path(outdir).mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    fname = f"{p.name}_all_variables_{slice_dir}{idx}_{timestamp}.{fmt}"
    path = Path(outdir) / fname
    fig.savefig(path, dpi=dpi if fmt.lower() in ["png", "jpg", "jpeg"] else None,
                bbox_inches="tight", facecolor="white")
    #print(f"Saved -> {path}")
    return path



# ---------------------------------------------------------------------
# _slice2d
# ---------------------------------------------------------------------
# Purpose:
#   Extract a correctly oriented 2D slice from a 3D array.
#
# What it does:
#   - Handles xz / xy / yz planes
#   - Returns metadata for axis labels and titles
#
# Why it exists:
#   Centralises slice orientation logic so all plots are consistent.
#
# Used by:
#   - plot_slices_all_vars
#   - native-resolution exporters
def _slice2d(A, plane, idx):
    """
    Return a 2D slice and the axis sizes for tick labelling.
    A is assumed to have shape (Nx, Ny, Nz) with axes (x, y, z).
    plane in {"xz","xy","yz"}.
    idx is the fixed index for the missing axis:
      - plane="xz" fixes y=idx
      - plane="xy" fixes z=idx
      - plane="yz" fixes x=idx
    Returns (Z, Nx_plot, Ny_plot, xlab, ylab, title_plane)
    where Z is oriented so that horizontal axis is the first letter of plane.
    """
    plane = plane.lower()
    if plane == "xz":
        # A[:, y, :] has shape (Nx, Nz) -> we want x horizontal, z vertical => transpose for imshow_with_cbar (which does Z.T)
        # Your imshow_with_cbar currently does imshow(Z.T), so here we return (Nx, Nz) like before.
        Z = A[:, idx, :]        # (Nx, Nz)
        Nx_plot, Ny_plot = Z.shape[0], Z.shape[1]
        xlab, ylab = "x index", "z index"
        title_plane = "(x, z)"
    elif plane == "xy":
        Z = A[:, :, idx]        # (Nx, Ny)
        Nx_plot, Ny_plot = Z.shape[0], Z.shape[1]
        xlab, ylab = "x index", "y index"
        title_plane = "(x, y)"
    elif plane == "yz":
        Z = A[idx, :, :]        # (Ny, Nz)
        # Here horizontal should be y, vertical z. But imshow_with_cbar uses Z.T,
        # so give it (Ny, Nz) and label accordingly.
        Nx_plot, Ny_plot = Z.shape[0], Z.shape[1]
        xlab, ylab = "y index", "z index"
        title_plane = "(y, z)"
    else:
        raise ValueError("plane must be one of {'xz','xy','yz'}")

    return Z, Nx_plot, Ny_plot, xlab, ylab, title_plane


# ---------------------------------------------------------------------
# plot_slices_all_vars
# ---------------------------------------------------------------------
# Purpose:
#   Produce the canonical 6-panel diagnostic plot from full 3D fields.
#   High-level plotting from full 3D arrays
#
# What it does:
#   - Extracts one plane
#   - Normalises u,v,w,b
#   - Log-scales ε and χ
#
# Why it exists:
#   This is the reference diagnostic figure used throughout the project.
#
# Used by:
#   - Early notebooks
#   - Validation runs
def plot_slices_all_vars(
    p,
    u, v, w, b, eps, chi,
    Ek, Ep, N2,
    eps_avg, chi_avg,
    plane="xz",
    idx=None,
    figsize=(10, 16),
    save=False,
    outdir="figures",
    fmt="jpg",
    dpi=300,

    # ---- NEW explicit color limits ----
    u_lim=(-5, 5),
    v_lim=(-5, 5),
    w_lim=(-5, 5),
    b_lim=(-5, 5),
    eps_lim=(-2, 2),
    chi_lim=(-2, 3),
):
    """
    Plot 6 panels: u,v,w,b,log10(eps/<eps>),log10(chi/<chi>) on a chosen plane.

    Assumes fields have shape (Nx, Ny, Nz) with axes (x,y,z).
    plane: "xz", "xy", or "yz"
    idx: index along the missing axis (y for xz, z for xy, x for yz). Defaults to mid-plane.
    outpath: if provided, saves the figure.
    Returns (fig, axs).
    """
    plane = plane.lower()
    if idx is None:
        if plane == "xz":
            idx = p.Ny // 2
        elif plane == "xy":
            idx = p.Nz // 2
        elif plane == "yz":
            idx = p.Nx // 2

    fig, axs = plt.subplots(6, 1, figsize=figsize)
    fig.subplots_adjust(hspace=0.55)

    panels = [
        (u / np.sqrt(Ek),          "seismic", *u_lim,   r"$u'/E_k^{1/2}$", r"$u'$"),
        (v / np.sqrt(Ek),          "seismic", *v_lim,   r"$v'/E_k^{1/2}$", r"$v'$"),
        (w / np.sqrt(Ek),          "seismic", *w_lim,   r"$w'/E_k^{1/2}$", r"$w'$"),
        (b / np.sqrt(N2 * Ep),     "viridis", *b_lim,   r"$b'/(N E_p^{1/2})$", r"$b'$"),
        (np.log10(eps / eps_avg),  "magma",   *eps_lim,
         r"$\log_{10}(\varepsilon/\langle\varepsilon\rangle)$", r"$\varepsilon$"),
        (np.log10(chi / chi_avg),  "hot",     *chi_lim,
         r"$\log_{10}(\chi/\langle\chi\rangle)$", r"$\chi$"),
    ]

    for i, (A, cmap, vmin, vmax, cbar_lab, short_name) in enumerate(panels):
        Z, Nx_plot, Ny_plot, xlab, ylab, title_plane = _slice2d(A, plane, idx)

        imshow_with_cbar(axs[i], Z, cmap, vmin, vmax, cbar_lab)

        if plane == "xz":
            fixed = f"iy = {idx}"
        elif plane == "xy":
            fixed = f"iz = {idx}"
        else:  # "yz"
            fixed = f"ix = {idx}"

        axs[i].set_title(f"{short_name}{title_plane} at {fixed}")

        set_index_axis(axs[i], "x", Nx_plot, " " if i < 4 else xlab)
        set_index_axis(axs[i], "y", Ny_plot, ylab)

    # Optional save using your naming convention
    if save:
        if plane == "xz":
            slice_dir = "y"
            fixed_label = "iy"
        elif plane == "xy":
            slice_dir = "z"
            fixed_label = "iz"
        elif plane == "yz":
            slice_dir = "x"
            fixed_label = "ix"
        else:
            raise ValueError("plane must be one of {'xz','xy','yz'}")

        path = save_slice_figure(
            fig,
            p,
            slice_dir=slice_dir,
            idx=idx,
            outdir=outdir,
            fmt=fmt,
            dpi=dpi,
        )
        print(f"Saved -> {path}")

    return fig, axs

# ---------------------------------------------------------------------
# plot_slices_native_resolution
# ---------------------------------------------------------------------
# Purpose:
#   Export each field (u, v, w, b, eps, chi) from a single 2D slice
#   as a separate PNG image at *native grid resolution*.
#
# What it does:
#   - Extracts a single 2D slice from 3D fields on a chosen plane
#   - Applies the same normalisations as plot_slices_all_vars:
#       * u,v,w  -> divide by sqrt(Ek)
#       * b      -> divide by sqrt(N^2 Ep)
#       * eps    -> log10(eps / <eps>)
#       * chi    -> log10(chi / <chi>)
#   - Writes one PNG per variable with:
#       * 1 pixel = 1 grid point
#       * no axes, no interpolation, no resampling
#       * fixed colormap and vmin/vmax
#
# Why it exists:
#   This is for *data products*, not exploratory plots:
#     - movies and animations
#     - ML / image-based analysis
#     - pixel-accurate figures for papers
#
#   Unlike plot_slices_all_vars:
#     - no matplotlib layout
#     - no colorbars
#     - no DPI dependence
#     - output size equals DNS grid size
#
# Used by:
#   - Standalone export of high-resolution slices
#   - Batch processing of cases for visual archives
#
# Implementation notes:
#   - Orientation matches imshow(Z.T, origin="lower")
#   - Uses save_field_native_pixels internally
#   - File naming encodes case, variable, plane, index, and timestamp
#
# Important:
#   This function *materialises full-resolution 2D arrays*.
#   Do NOT use it on very large planes unless you intend to export them.
def plot_slices_native_resolution(
    p,
    u, v, w, b, eps, chi,
    Ek, Ep, N2,
    eps_avg, chi_avg,
    plane="xz",
    idx=None,
    outdir="figures",
    prefix=None,

    # ---- NEW explicit color limits ----
    u_lim=(-5, 5),
    v_lim=(-5, 5),
    w_lim=(-5, 5),
    b_lim=(-5, 5),
    eps_lim=(-2, 2),
    chi_lim=(-2, 3),
):
    """
    Export u,v,w,b,eps,chi as separate native-resolution PNGs (no axes).
    1 pixel = 1 grid point in the exported 2D slice.

    Files are written as RGBA PNGs with colormaps and fixed vmin/vmax:
      u,v,w : seismic, [-5, 5] with u/sqrt(Ek)
      b     : viridis, [-5, 5] with b/sqrt(N2*Ep)
      eps   : magma,  [-2, 2] with log10(eps/eps_avg)
      chi   : hot,    [-2, 2] with log10(chi/chi_avg)
    """
    plane = plane.lower()
    if idx is None:
        idx = {"xz": p.Ny // 2, "xy": p.Nz // 2, "yz": p.Nx // 2}[plane]

    outdir = Path(outdir)
    outdir.mkdir(parents=True, exist_ok=True)

    # nice filename prefix
    if prefix is None:
        # slice_dir is the fixed axis
        slice_dir = {"xz": "y", "xy": "z", "yz": "x"}[plane]
        prefix = f"{p.name}_{plane}_i{slice_dir}{idx}"

    # Build the six 2D slices in the same orientation you see in imshow_with_cbar:
    # imshow_with_cbar does imshow(Z.T), so for a consistent visual, we export Z.T
    def _Z(A):
        Z, *_ = _slice2d(A, plane, idx)   # this is what you pass to imshow_with_cbar
        return np.flipud(Z.T)             # matches imshow(Z.T, origin="lower")

    # Fields to export: (name, array2d, cmap, vmin, vmax)
    items = [
        ("u", _Z(u / np.sqrt(Ek)),          "seismic", *u_lim),
        ("v", _Z(v / np.sqrt(Ek)),          "seismic", *v_lim),
        ("w", _Z(w / np.sqrt(Ek)),          "seismic", *w_lim),
    
        ("b", _Z(b / np.sqrt(N2 * Ep)),     "viridis", *b_lim),
    
        ("e", _Z(np.log10(eps / eps_avg)),  "magma",   *eps_lim),
    
        ("c", _Z(np.log10(chi / chi_avg)),  "hot",     *chi_lim),
    ]
    slice_dir = {"xz": "y", "xy": "z", "yz": "x"}[plane]
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    paths = {}
    for name, Z2, cmap, vmin, vmax in items:
        fname = f"{p.name}_{name}_native_res_{slice_dir}{idx}_{timestamp}.png"
        path = outdir / fname
        save_field_native_pixels(Z2, str(path), cmap=cmap, vmin=vmin, vmax=vmax)
        paths[name] = str(path)
    return paths



# ---------------------------------------------------------------------
# save_field_native_pixels
# ---------------------------------------------------------------------
# Purpose:
#   Save a 2D numerical field as a pixel-perfect PNG image.
#
# What it does:
#   - Maps a 2D NumPy array directly to RGBA pixels (1 array cell = 1 pixel)
#   - Applies a matplotlib colormap with fixed vmin/vmax
#   - Writes an RGBA PNG with no interpolation or rescaling
#   - Optionally renders NaNs as transparent pixels
#
# Why it exists:
#   This is used when you want *exact spatial fidelity*:
#     - movies
#     - machine-learning datasets
#     - paper figures where each pixel corresponds to one grid point
#
#   Unlike imshow-based plotting, this function:
#     - does NOT resample
#     - does NOT depend on figure DPI
#     - preserves the native DNS resolution exactly
#
# Used by:
#   - plot_slices_native_resolution
#   - export_native_resolution_from_bundle
#   - export_native_resolution_from_bundle_multi
#
# Notes:
#   The input array Z must already be oriented correctly
#   (usually Z.T flipped vertically to match imshow(origin="lower")).
def save_field_native_pixels(
    Z,
    path,
    cmap="viridis",
    vmin=None,
    vmax=None,
    nan_color=(0, 0, 0, 0),  # transparent for NaNs
):
    """
    Save a 2D array as a PNG with native resolution:
    1 array element -> 1 output pixel. No interpolation.

    Z must be 2D. Output is RGBA PNG.
    """
    Z = np.asarray(Z)
    if Z.ndim != 2:
        raise ValueError(f"Z must be 2D, got shape {Z.shape}")

    if vmin is None:
        vmin = np.nanmin(Z)
    if vmax is None:
        vmax = np.nanmax(Z)
    if not np.isfinite(vmin) or not np.isfinite(vmax) or vmin == vmax:
        raise ValueError(f"Bad vmin/vmax: vmin={vmin}, vmax={vmax}")

    cmap_obj = cm.get_cmap(cmap) if isinstance(cmap, str) else cmap
    norm = colors.Normalize(vmin=vmin, vmax=vmax, clip=True)

    rgba = cmap_obj(norm(Z))  # float RGBA in [0,1], shape (H,W,4)

    nan_mask = ~np.isfinite(Z)
    if np.any(nan_mask):
        r, g, b, a = [c / 255.0 for c in nan_color]
        rgba[nan_mask] = (r, g, b, a)

    rgba8 = (rgba * 255).astype(np.uint8)
    Image.fromarray(rgba8, mode="RGBA").save(path)
    return path


# ============================================================
# Lazy loading utilities (memmap-based, slice-level I/O)
# ============================================================

from dataclasses import dataclass
from typing import Tuple, Optional, Dict
import numpy as np

# ---------------------------------------------------------------------
# LazyField
# ---------------------------------------------------------------------
# Purpose:
#   Lazy, slice-level access to massive 3D DNS fields on disk.
#
# What it does:
#   - Memory-maps raw binary files
#   - Only materialises requested 2D slices
#
# Why it exists:
#   Makes analysis feasible for 10^10+ grid point simulations.
#
# Used by:
#   - All NetCDF export routines
#   - Lazy plotting pipelines
@dataclass
class LazyField:
    """
    Lazy access to one variable stored as a raw binary float32 Fortran-order array
    shaped (Nx+2, Ny, Nz), with two padded x-rows dropped on read.

    Mirrors current load_binary assumptions exactly.
    """
    filepath: str
    shape_file: Tuple[int, int, int]          # (Nx+2, Ny, Nz)
    dtype: np.dtype = np.float32
    order: str = "F"
    drop_last_x: int = 2

    _mm: Optional[np.memmap] = None

    def open(self) -> "LazyField":
        if self._mm is None:
            self._mm = np.memmap(
                self.filepath,
                dtype=self.dtype,
                mode="r",
                shape=self.shape_file,
                order=self.order,
            )
        return self

    @property
    def mm(self) -> np.memmap:
        if self._mm is None:
            self.open()
        return self._mm

    @property
    def shape(self) -> Tuple[int, int, int]:
        Nx_file, Ny, Nz = self.shape_file
        return (Nx_file - self.drop_last_x, Ny, Nz)

    def slice2d(
        self,
        plane: str = "xz",
        idx: Optional[int] = None,
        stride: Tuple[int, int, int] = (1, 1, 1),
    ) -> np.ndarray:
        """
        Return a 2D numpy array (materialised) for plotting.

        plane: 'xz', 'xy', or 'yz'
        idx: index along missing axis
        stride: (sx, sy, sz) subsampling along (x, y, z)
        """
        plane = plane.lower()
        sx, sy, sz = stride
        Nx, Ny, Nz = self.shape

        if plane == "xz":
            if idx is None:
                idx = Ny // 2
            return np.asarray(self.mm[:Nx:sx, idx:idx+1:sy, :Nz:sz][:, 0, :])

        if plane == "xy":
            if idx is None:
                idx = Nz // 2
            return np.asarray(self.mm[:Nx:sx, :Ny:sy, idx:idx+1:sz][:, :, 0])

        if plane == "yz":
            if idx is None:
                idx = Nx // 2
            return np.asarray(self.mm[idx:idx+1:sx, :Ny:sy, :Nz:sz][0, :, :])

        raise ValueError("plane must be one of {'xz','xy','yz'}")

# ---------------------------------------------------------------------
# open_lazy_field / open_lazy_fields
# ---------------------------------------------------------------------
# Purpose:
#   Convenience constructors for LazyField objects.
#
# Why they exist:
#   Avoid boilerplate and ensure consistent file layout assumptions.
#
# Used by:
#   - All modern notebooks
#   - Export scripts
def open_lazy_field(varName: str, p, dtype=np.float32) -> LazyField:
    """
    Open one variable lazily using the existing file naming and layout.
    """
    filepath = p.dirPath + varName + "_" + p.tStamp
    return LazyField(
        filepath=filepath,
        shape_file=(p.Nx + 2, p.Ny, p.Nz),
        dtype=dtype,
        order="F",
        drop_last_x=2,
    ).open()

def open_lazy_fields(varNames, p, dtype=np.float32) -> Dict[str, LazyField]:
    """
    Convenience helper to open multiple lazy fields at once.
    """
    return {name: open_lazy_field(name, p, dtype=dtype) for name in varNames}

# ---------------------------------------------------------------------
# plot_slices_all_vars_lazy
# ---------------------------------------------------------------------
# Purpose:
#   Memory-safe version of plot_slices_all_vars that never loads full 3D arrays.
#
# What it does:
#   - Uses LazyField.slice2d to read only ONE 2D slice per variable from disk
#   - Applies the same normalisations/logs as the full-resolution plotting:
#       u,v,w  -> /sqrt(Ek)
#       b      -> /sqrt(N^2 Ep)
#       eps    -> log10(eps/<eps>)
#       chi    -> log10(chi/<chi>)
#   - Plots the 6-panel diagnostic figure from these small 2D arrays
#
# Why it exists:
#   Frontier-scale runs make full 3D arrays impossible to hold in RAM.
#   This keeps I/O and memory proportional to the slice size, not Nx*Ny*Nz.
#
# Used by:
#   - adrienLazyVisualizeData.ipynb (or any quick diagnostic notebook)
#   - Rapid browsing of cases/timestamps without pre-exporting NetCDF
def plot_slices_all_vars_lazy(
    p,
    fields,                 # dict: {"u": LazyField, "v": ..., "eps": ...}
    Ek, Ep, N2,
    eps_avg, chi_avg,
    plane="xz",
    idx=None,
    stride=(1, 1, 1),
    figsize=(10, 16),
    save=False,
    outdir="figures",
    fmt="jpg",
    dpi=300,

    u_lim=(-5, 5),
    v_lim=(-5, 5),
    w_lim=(-5, 5),
    b_lim=(-5, 5),
    eps_lim=(-2, 2),
    chi_lim=(-2, 3),
):
    """
    Lazy plotting: reads ONLY the required 2D slices (with stride) from memmap,
    then computes normalisations/logs on those 2D arrays and plots 6 panels.
    """
    plane = plane.lower()

    # --- Pull 2D slices only (materialise small arrays) ---
    u2   = fields["u"].slice2d(plane=plane, idx=idx, stride=stride)
    v2   = fields["v"].slice2d(plane=plane, idx=idx, stride=stride)
    w2   = fields["w"].slice2d(plane=plane, idx=idx, stride=stride)
    b2   = fields["b"].slice2d(plane=plane, idx=idx, stride=stride)
    eps2 = fields["eps"].slice2d(plane=plane, idx=idx, stride=stride)
    chi2 = fields["chi"].slice2d(plane=plane, idx=idx, stride=stride)

    # --- Derived plotted fields (2D only) ---
    with np.errstate(divide="ignore", invalid="ignore"):
        U = u2 / np.sqrt(Ek)
        V = v2 / np.sqrt(Ek)
        W = w2 / np.sqrt(Ek)
        B = b2 / np.sqrt(N2 * Ep)
        E = np.log10(eps2 / eps_avg)
        C = np.log10(chi2 / chi_avg)

    panels = [
        (U, "seismic", u_lim,  r"$u'/E_k^{1/2}$"),
        (V, "seismic", v_lim,  r"$v'/E_k^{1/2}$"),
        (W, "seismic", w_lim,  r"$w'/E_k^{1/2}$"),
        (B, "viridis", b_lim,  r"$b'/(N E_p^{1/2})$"),
        (E, "magma",   eps_lim, r"$\log_{10}(\varepsilon/\langle\varepsilon\rangle)$"),
        (C, "hot",     chi_lim, r"$\log_{10}(\chi/\langle\chi\rangle)$"),
    ]

    fig, axs = plt.subplots(6, 1, figsize=figsize)
    fig.subplots_adjust(hspace=0.55)

    for ax, (Z, cmap, lim, title) in zip(axs, panels):
        vmin, vmax = lim
        im = ax.imshow(Z.T, origin="lower", aspect="auto", cmap=cmap, vmin=vmin, vmax=vmax)
        ax.set_title(f"{title} | plane={plane}, idx={idx}, stride={stride}")
        plt.colorbar(im, ax=ax, fraction=0.046, pad=0.04)

    if save:
        import os
        os.makedirs(outdir, exist_ok=True)
        fname = f"slices_{plane}_idx{idx}_stride{stride[0]}-{stride[1]}-{stride[2]}.{fmt}"
        fig.savefig(os.path.join(outdir, fname), dpi=dpi, bbox_inches="tight")

    return fig, axs

# ---------------------------------------------------------------------
# mean3d_strided
# ---------------------------------------------------------------------
# Purpose:
#   Fast approximate volume-mean of a LazyField without reading the full cube.
#
# What it does:
#   - Reads a regularly subsampled 3D array from the memmap (stride in x,y,z)
#   - Computes the mean of that sample as an approximation of the true mean
#
# Why it exists:
#   Exact means require reading Nx*Ny*Nz values (too much I/O).
#   A strided sample is usually enough for quick Ek/Ep/normalisation estimates.
#
# Used by:
#   - Quick stats for normalisations when you don’t want to precompute globals
#   - Sanity checks and interactive exploration
def mean3d_strided(field: LazyField, stride: Tuple[int, int, int] = (2, 2, 2)) -> float:
    """
    Approx mean using regular subsampling.
    Much less I/O than exact mean.

    stride is (sx, sy, sz).
    """
    sx, sy, sz = stride
    Nx, Ny, Nz = field.shape
    mm = field.mm

    # Note: we only access up to Nx (drop padding), then stride
    sample = np.asarray(mm[:Nx:sx, :Ny:sy, :Nz:sz], dtype=np.float64)
    return float(sample.mean())

# ---------------------------------------------------------------------
# mean3d_strided_power
# ---------------------------------------------------------------------
# Purpose:
#   Fast approximate mean of (field**power) using strided subsampling.
#
# What it does:
#   - Reads a strided 3D sample from disk (like mean3d_strided)
#   - Raises to `power` and averages
#
# Why it exists:
#   Many diagnostics use second moments (variance/energy-like quantities).
#   This gives an inexpensive estimate without full-volume I/O.
#
# Used by:
#   - Rough Ek-like / variance-like estimates from LazyFields
#   - Quick comparisons across cases
def mean3d_strided_power(
    field: LazyField,
    power: int = 2,
    stride=(2, 2, 2),
) -> float:
    """
    Approximate mean of field**power using regular subsampling.
    """
    sx, sy, sz = stride
    Nx, Ny, Nz = field.shape
    mm = field.mm

    sample = np.asarray(mm[:Nx:sx, :Ny:sy, :Nz:sz], dtype=np.float64)
    return float((sample ** power).mean())

# ---------------------------------------------------------------------
# VarSlices
# ---------------------------------------------------------------------
# Purpose:
#   Store one variable across multiple planes.
#
# What it does:
#   - Allows access like s.u.xz or s.epslog.xy
#
# Why it exists:
#   Makes multi-plane plotting and exporting clean and explicit.
class VarSlices:
    def __init__(self, name: str):
        self.name = name
        self._planes: Dict[str, np.ndarray] = {}

    def set(self, plane: str, arr2d: np.ndarray):
        self._planes[plane.lower()] = arr2d

    def __getattr__(self, plane: str) -> np.ndarray:
        plane = plane.lower()
        if plane in self._planes:
            return self._planes[plane]
        raise AttributeError(
            f"{self.name} has no slice for plane '{plane}'. Available: {list(self._planes.keys())}"
        )

    def available(self):
        return list(self._planes.keys())

# ---------------------------------------------------------------------
# SliceBundle
# ---------------------------------------------------------------------
# Purpose:
#   Bundle multiple variables and planes with shared metadata.
#
# What it does:
#   - Stores VarSlices
#   - Carries idx and stride information
#
# Why it exists:
#   This is the main object passed between notebooks and plotting routines.
@dataclass
class SliceBundle:
    """
    Access variables as attributes (s.u, s.r, ...), then planes (s.u.xz, s.u.xy, ...).
    Also contains per-plane metadata: idx and stride.
    """
    vars: Dict[str, VarSlices]
    idx: Dict[str, int]
    stride: Tuple[int, int, int]

    def __getattr__(self, var: str) -> VarSlices:
        if var in self.vars:
            return self.vars[var]
        raise AttributeError(f"No variable '{var}'. Available: {list(self.vars.keys())}")

    def available_vars(self):
        return list(self.vars.keys())

    def available_planes(self):
        # infer from first variable
        if not self.vars:
            return []
        first = next(iter(self.vars.values()))
        return first.available()

# ---------------------------------------------------------------------
# default_idx_for_plane
# ---------------------------------------------------------------------
# Purpose:
#   Standard rule for "mid-plane" slicing in each coordinate plane.
#
# What it does:
#   - Returns Ny//2 for xz
#   - Returns Nz//2 for xy
#   - Returns Nx//2 for yz
#
# Why it exists:
#   Centralises the convention so every notebook picks the same default slice.
#
# Used by:
#   - get_slices_multi
#   - get_derived_slices_multi
#   - plot/export helpers when idx is not specified
def default_idx_for_plane(p, plane: str) -> int:
    plane = plane.lower()
    if plane == "xz":
        return p.Ny // 2
    if plane == "xy":
        return p.Nz // 2
    if plane == "yz":
        return p.Nx // 2
    raise ValueError("plane must be one of {'xz','xy','yz'}")

# ---------------------------------------------------------------------
# get_slices_multi
# ---------------------------------------------------------------------
# Purpose:
#   Read many variables and many planes into one structured container.
#
# What it does:
#   - For each requested plane (xz/xy/yz) and each requested variable:
#       reads a 2D slice from LazyField.slice2d
#   - Stores results in a SliceBundle so you can access:
#       s.u.xz, s.r.xy, ...
#   - Carries per-plane idx metadata and the stride used
#
# Why it exists:
#   Avoids repeated slice reads scattered across notebooks and keeps
#   multi-plane work explicit and reproducible.
#
# Used by:
#   - NetCDF export / derived-field pipelines
#   - Any notebook that wants xz+xy+yz views without manual bookkeeping
def get_slices_multi(
    fields,
    p,
    planes: Union[str, Iterable[str]] = ("xz",),
    idx: Optional[Union[int, Dict[str, int]]] = None,
    stride: Tuple[int, int, int] = (1, 1, 1),
    varnames: Optional[Iterable[str]] = None,
) -> SliceBundle:
    """
    Read 2D slices for multiple planes into one object.

    planes: e.g. ["xz","xy"] or "xz"
    idx:
      - None: uses default mid-plane index per plane
      - int: uses same idx for all planes (rarely what you want, but supported)
      - dict: {"xz": iy, "xy": iz, "yz": ix}
    """
    if isinstance(planes, str):
        planes = [planes]
    planes = [pl.lower() for pl in planes]

    if varnames is None:
        varnames = list(fields.keys())

    # build idx per plane
    idx_map: Dict[str, int] = {}
    if idx is None:
        for pl in planes:
            idx_map[pl] = default_idx_for_plane(p, pl)
    elif isinstance(idx, int):
        for pl in planes:
            idx_map[pl] = idx
    else:
        # dict provided
        for pl in planes:
            idx_map[pl] = idx.get(pl, default_idx_for_plane(p, pl))

    # allocate VarSlices for each variable
    varslices: Dict[str, VarSlices] = {name: VarSlices(name) for name in varnames}

    # read requested planes
    for pl in planes:
        for name in varnames:
            arr2d = fields[name].slice2d(plane=pl, idx=idx_map[pl], stride=stride)
            varslices[name].set(pl, arr2d)

    return SliceBundle(vars=varslices, idx=idx_map, stride=stride)

# ---------------------------------------------------------------------
# add_derived_multi
# ---------------------------------------------------------------------
# Purpose:
#   Add the standard derived/normalised diagnostics to an existing SliceBundle.
#
# What it does:
#   - Takes raw slices already stored in `slices`
#   - Computes (for every available plane):
#       uN, vN, wN   : velocity / sqrt(Ek)
#       bN           : buoyancy / sqrt(N^2 Ep) using b = -g r
#       epslog       : log10(eps/<eps>)
#       chilog       : log10(chi/<chi>)
#   - Optionally keeps the raw fields too (include_raw=True)
#
# Why it exists:
#   Separates “I/O step” (read raw slices) from “diagnostic step”
#   (construct the plotted quantities), making pipelines cleaner.
#
# Used by:
#   - Workflows where you first load raw slices, then compute diagnostics
#   - Multi-plane plotting/export from a single bundle
def add_derived_multi(slices: SliceBundle, p, stats: dict, tiny: float = 1e-30,
                      include_raw: bool = True) -> SliceBundle:
    """
    Add derived/normalised fields to a multi-plane SliceBundle.

    Requires raw variables to exist in slices:
      u, v, w, r, ee, chi

    Adds (for every available plane):
      uN, vN, wN, bN, epslog, chilog

    stats must contain:
      Ek, Ep, eps_avg, chi_avg
    """
    Ek = stats["Ek"]
    Ep = stats["Ep"]
    eps_avg = stats["eps_avg"]
    chi_avg = stats["chi_avg"]

    planes = slices.available_planes()

    # start with either raw vars or empty
    out_vars: Dict[str, VarSlices] = {}
    if include_raw:
        out_vars.update(slices.vars)

    def _ensure_var(name: str) -> VarSlices:
        if name not in out_vars:
            out_vars[name] = VarSlices(name)
        return out_vars[name]

    # loop planes and build derived 2D arrays plane-by-plane
    for pl in planes:
        u2   = getattr(slices.u, pl)
        v2   = getattr(slices.v, pl)
        w2   = getattr(slices.w, pl)
        r2   = getattr(slices.r, pl)
        ee2  = getattr(slices.ee, pl)
        chi2 = getattr(slices.chi, pl)

        _ensure_var("uN").set(pl, u2 / np.sqrt(Ek))
        _ensure_var("vN").set(pl, v2 / np.sqrt(Ek))
        _ensure_var("wN").set(pl, w2 / np.sqrt(Ek))

        # buoyancy b = -g r, then normalise by sqrt(N^2 Ep)
        _ensure_var("bN").set(pl, r2 * (-p.zAccel) / np.sqrt(p.N2 * Ep))

        with np.errstate(divide="ignore", invalid="ignore"):
            _ensure_var("epslog").set(pl, np.log10(np.maximum(ee2, tiny) / eps_avg))
            _ensure_var("chilog").set(pl, np.log10(np.maximum(chi2, tiny) / chi_avg))

    return SliceBundle(vars=out_vars, idx=slices.idx, stride=slices.stride)

# ---------------------------------------------------------------------
# get_derived_slices_multi
# ---------------------------------------------------------------------
# Purpose:
#   Build derived 2D diagnostic fields directly from 3D LazyFields.
#
# What it does:
#   - Reads only required slices
#   - Computes uN, vN, wN, bN, epslog, chilog
#
# Why it exists:
#   Avoids storing raw slices in memory and enables fast iteration.
#
# Used by:
#   - Pre-NetCDF workflows
def get_derived_slices_multi(
    fields,
    p,
    stats: dict,
    planes=("xz",),
    idx=None,
    stride=(1, 1, 1),
    tiny: float = 1e-30,
    verbose: bool = False,          # <-- ADD
    progress_every: int = 1,        # <-- ADD (prints every plane by default)
):
    ...
    if isinstance(planes, str):
        planes = [planes]
    planes = [pl.lower() for pl in planes]

    # idx map ... (unchanged)

    Ek = stats["Ek"]; Ep = stats["Ep"]
    eps_avg = stats["eps_avg"]; chi_avg = stats["chi_avg"]

    out_vars: Dict[str, VarSlices] = {name: VarSlices(name) for name in
                                     ["uN", "vN", "wN", "bN", "epslog", "chilog"]}

    nplanes = len(planes)

    # ---- build idx_map (THIS WAS MISSING) ----
    idx_map: Dict[str, int] = {}
    
    if idx is None:
        for pl in planes:
            idx_map[pl] = default_idx_for_plane(p, pl)
    elif isinstance(idx, int):
        for pl in planes:
            idx_map[pl] = idx
    else:
        for pl in planes:
            idx_map[pl] = idx.get(pl, default_idx_for_plane(p, pl))
        
    for ip, pl in enumerate(planes, start=1):
        ii = idx_map[pl]

        if verbose and ((ip-1) % progress_every == 0):
            print(f"[get_derived_slices_multi] plane {ip}/{nplanes} '{pl}' idx={ii} stride={stride}", flush=True)

        # read only what we need, as 2D arrays
        if verbose:
            print("  reading: u,v,w,r,ee,chi ...", flush=True)

        u2   = fields["u"].slice2d(pl, ii, stride)
        v2   = fields["v"].slice2d(pl, ii, stride)
        w2   = fields["w"].slice2d(pl, ii, stride)
        r2   = fields["r"].slice2d(pl, ii, stride)
        ee2  = fields["ee"].slice2d(pl, ii, stride)
        chi2 = fields["chi"].slice2d(pl, ii, stride)

        if verbose:
            print("  computing derived fields ...", flush=True)

        out_vars["uN"].set(pl, u2 / np.sqrt(Ek))
        out_vars["vN"].set(pl, v2 / np.sqrt(Ek))
        out_vars["wN"].set(pl, w2 / np.sqrt(Ek))
        out_vars["bN"].set(pl, r2 * (-p.zAccel) / np.sqrt(p.N2 * Ep))

        with np.errstate(divide="ignore", invalid="ignore"):
            out_vars["epslog"].set(pl, np.log10(np.maximum(ee2, tiny) / eps_avg))
            out_vars["chilog"].set(pl, np.log10(np.maximum(chi2, tiny) / chi_avg))

        if verbose:
            print(f"  done plane '{pl}'", flush=True)

    if verbose:
        print("[get_derived_slices_multi] done.", flush=True)

    return SliceBundle(vars=out_vars, idx=idx_map, stride=stride)
    
# ---------------------------------------------------------------------
# plot_slices_derived_bundle
# ---------------------------------------------------------------------
# Purpose:
#   Canonical 6-panel diagnostic plot, but using derived fields already computed.
#
# What it does:
#   - Expects a SliceBundle containing uN,vN,wN,bN,epslog,chilog (2D arrays)
#   - Plots the same 6 panels and uses the same tick labelling + save convention
#
# Why it exists:
#   When derived fields are precomputed (via get_derived_slices_multi or add_derived_multi),
#   plotting should not need access to the raw 3D data anymore.
#
# Used by:
#   - NetCDF-based notebooks (load slice -> derive -> plot)
#   - Any workflow where you want consistent figures from cached derived slices
def plot_slices_derived_bundle(
    p,
    s,                      # SliceBundle with vars uN,vN,wN,bN,epslog,chilog
    plane="xz",
    idx=None,               # optional override; otherwise uses s.idx[plane]
    figsize=(10, 16),
    save=False,
    outdir="figures",
    fmt="png",
    dpi=300,

    # same default limits as before
    u_lim=(-5, 5),
    v_lim=(-5, 5),
    w_lim=(-5, 5),
    b_lim=(-5, 5),
    eps_lim=(-2, 2),
    chi_lim=(-2, 3),
):
    """
    Reproduce plot_slices_all_vars style, but from a derived SliceBundle.

    Expects s to contain:
      uN, vN, wN, bN, epslog, chilog
    Each is a VarSlices with planes xz/xy/yz.

    Plots 6 panels in a column, with the same axis ticks + save naming convention.
    """
    plane = plane.lower()

    # choose idx for the title/saving label
    if idx is None:
        if hasattr(s, "idx") and plane in s.idx:
            idx = s.idx[plane]
        else:
            idx = default_idx_for_plane(p, plane)

    fig, axs = plt.subplots(6, 1, figsize=figsize)
    fig.subplots_adjust(hspace=0.55)

    panels = [
        (getattr(s.uN,     plane), "seismic", *u_lim,   r"$u'/E_k^{1/2}$", r"$u_N$"),
        (getattr(s.vN,     plane), "seismic", *v_lim,   r"$v'/E_k^{1/2}$", r"$v_N$"),
        (getattr(s.wN,     plane), "seismic", *w_lim,   r"$w'/E_k^{1/2}$", r"$w_N$"),
        (getattr(s.bN,     plane), "viridis", *b_lim,   r"$b'/(N E_p^{1/2})$", r"$b_N$"),
        (getattr(s.epslog, plane), "magma",   *eps_lim,
         r"$\log_{10}(\varepsilon/\langle\varepsilon\rangle)$", r"$\varepsilon$"),
        (getattr(s.chilog, plane), "hot",     *chi_lim,
         r"$\log_{10}(\chi/\langle\chi\rangle)$", r"$\chi$"),
    ]

    for i, (Z, cmap, vmin, vmax, cbar_lab, short_name) in enumerate(panels):
        # Z is already 2D (not 3D), but we want the same labeling logic as _slice2d()
        Nx_plot, Ny_plot = Z.shape[0], Z.shape[1]
        if plane == "xz":
            xlab, ylab, title_plane, fixed = "x index", "z index", "(x, z)", f"iy = {idx}"
        elif plane == "xy":
            xlab, ylab, title_plane, fixed = "x index", "y index", "(x, y)", f"iz = {idx}"
        else:
            xlab, ylab, title_plane, fixed = "y index", "z index", "(y, z)", f"ix = {idx}"

        imshow_with_cbar(axs[i], Z, cmap, vmin, vmax, cbar_lab)
        axs[i].set_title(f"{short_name}{title_plane} at {fixed}")

        set_index_axis(axs[i], "x", Nx_plot, " " if i < 4 else xlab)
        set_index_axis(axs[i], "y", Ny_plot, ylab)

    if save:
        slice_dir = {"xz": "y", "xy": "z", "yz": "x"}[plane]
        path = save_slice_figure(fig, p, slice_dir=slice_dir, idx=idx, outdir=outdir, fmt=fmt, dpi=dpi)
        print(f"Saved -> {path}")

    return fig, axs

# ---------------------------------------------------------------------
# plot_slices_derived_bundle_multi
# ---------------------------------------------------------------------
# Purpose:
#   Convenience wrapper to produce derived 6-panel figures for multiple planes.
#
# What it does:
#   - Loops over planes (e.g. xz, xy, yz)
#   - Calls plot_slices_derived_bundle for each
#   - Returns a dict of (fig, axs) keyed by plane
#
# Why it exists:
#   Makes “make all three planes” one call, with consistent idx selection.
#
# Used by:
#   - Quick production of a full diagnostic set (xz/xy/yz) for a case
def plot_slices_derived_bundle_multi(
    p,
    s,
    planes=("xz", "xy", "yz"),
    idx=None,                 # None | int | dict like {"xz":iy,"xy":iz,"yz":ix}
    figsize=(10, 16),
    save=False,
    outdir="figures",
    fmt="png",
    dpi=300,
    **kwargs,                 # forwards u_lim, v_lim, ...
):
    """
    Plot the same 6-panel figure for multiple planes, using plot_slices_derived_bundle.

    Returns:
      figs: dict plane -> (fig, axs)
    """
    if isinstance(planes, str):
        planes = [planes]
    planes = [pl.lower() for pl in planes]

    # build idx map
    idx_map = {}
    if idx is None:
        for pl in planes:
            idx_map[pl] = s.idx.get(pl, default_idx_for_plane(p, pl)) if hasattr(s, "idx") else default_idx_for_plane(p, pl)
    elif isinstance(idx, int):
        for pl in planes:
            idx_map[pl] = idx
    else:
        for pl in planes:
            idx_map[pl] = idx.get(pl, s.idx.get(pl, default_idx_for_plane(p, pl)) if hasattr(s, "idx") else default_idx_for_plane(p, pl))

    figs = {}
    for pl in planes:
        fig, axs = plot_slices_derived_bundle(
            p, s,
            plane=pl,
            idx=idx_map[pl],
            figsize=figsize,
            save=save,
            outdir=outdir,
            fmt=fmt,
            dpi=dpi,
            **kwargs,
        )
        figs[pl] = (fig, axs)

    return figs

# ---------------------------------------------------------------------
# export_native_resolution_from_bundle
# ---------------------------------------------------------------------
# Purpose:
#   Export derived 2D diagnostics from a SliceBundle as native-resolution PNGs.
#
# What it does:
#   - Takes already-derived 2D arrays (uN,vN,wN,bN,epslog,chilog) from `s`
#   - Converts them into export-ready orientation matching imshow(origin="lower")
#   - Writes one PNG per variable via save_field_native_pixels
#
# Why it exists:
#   Once you have derived slices cached (or loaded from NetCDF),
#   you can export publication/ML-ready images without touching the 3D DNS files.
#
# Used by:
#   - NetCDF workflows producing image assets
#   - Batch export scripts after derived slice generation
def export_native_resolution_from_bundle(
    p,
    s,                      # SliceBundle with uN,vN,wN,bN,epslog,chilog
    plane="xz",
    idx=None,               # only for filenames; defaults to s.idx[plane]
    outdir="figures",

    u_lim=(-5, 5),
    v_lim=(-5, 5),
    w_lim=(-5, 5),
    b_lim=(-5, 5),
    eps_lim=(-2, 2),
    chi_lim=(-2, 3),
):
    plane = plane.lower()

    # idx is used only for naming; data comes from s.<var>.<plane>
    if idx is None:
        if hasattr(s, "idx") and plane in s.idx:
            idx = s.idx[plane]
        else:
            idx = default_idx_for_plane(p, plane)

    outdir = Path(outdir)
    outdir.mkdir(parents=True, exist_ok=True)

    slice_dir = {"xz": "y", "xy": "z", "yz": "x"}[plane]
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    # Match your old exporter orientation (imshow(Z.T, origin="lower"))
    def _export_ready(Z):
        return np.flipud(Z.T)

    items = [
        ("u", _export_ready(getattr(s.uN, plane)),     "seismic", *u_lim),
        ("v", _export_ready(getattr(s.vN, plane)),     "seismic", *v_lim),
        ("w", _export_ready(getattr(s.wN, plane)),     "seismic", *w_lim),
        ("b", _export_ready(getattr(s.bN, plane)),     "viridis", *b_lim),
        ("e", _export_ready(getattr(s.epslog, plane)), "magma",   *eps_lim),
        ("c", _export_ready(getattr(s.chilog, plane)), "hot",     *chi_lim),
    ]

    paths = {}
    for name, Z2, cmap, vmin, vmax in items:
        fname = f"{p.name}_{name}_native_res_{slice_dir}{idx}_{timestamp}.png"
        path = outdir / fname
        save_field_native_pixels(Z2, str(path), cmap=cmap, vmin=vmin, vmax=vmax)
        paths[name] = str(path)

    return paths

# ---------------------------------------------------------------------
# export_native_resolution_from_bundle_multi
# ---------------------------------------------------------------------
# Purpose:
#   Export native-resolution PNGs for multiple planes from one derived SliceBundle.
#
# What it does:
#   - Loops over planes (xz/xy/yz)
#   - Calls export_native_resolution_from_bundle for each
#   - Returns a dict: plane -> {varname: filepath}
#
# Why it exists:
#   One-call “export everything” for a case when derived slices are available.
#
# Used by:
#   - Batch figure generation / archiving
#   - Creating consistent datasets across planes
def export_native_resolution_from_bundle_multi(
    p,
    s,
    planes=("xz", "xy", "yz"),
    idx=None,               # None | int | dict per plane
    outdir="figures",
    **kwargs,               # forwards u_lim,...chi_lim
):
    if isinstance(planes, str):
        planes = [planes]
    planes = [pl.lower() for pl in planes]

    # idx map for filenames
    idx_map = {}
    if idx is None:
        for pl in planes:
            if hasattr(s, "idx") and pl in s.idx:
                idx_map[pl] = s.idx[pl]
            else:
                idx_map[pl] = default_idx_for_plane(p, pl)
    elif isinstance(idx, int):
        for pl in planes:
            idx_map[pl] = idx
    else:
        for pl in planes:
            fallback = s.idx[pl] if (hasattr(s, "idx") and pl in s.idx) else default_idx_for_plane(p, pl)
            idx_map[pl] = idx.get(pl, fallback)

    out = {}
    for pl in planes:
        out[pl] = export_native_resolution_from_bundle(
            p, s,
            plane=pl,
            idx=idx_map[pl],
            outdir=outdir,
            **kwargs,
        )
    return out

# ---------------------------------------------------------------------
# coords_1d
# ---------------------------------------------------------------------
# Purpose:
#   Construct 1D coordinate vectors consistent with the solver grid.
#
# What it does:
#   - Returns uniform x,y,z vectors spanning [0, L) with endpoint=False
#   - Uses Nx,Ny,Nz and Lx,Ly,Lz from p
#
# Why it exists:
#   NetCDF outputs should carry physical coordinates, not only index space.
#   This provides small, reliable coordinate arrays for exported 2D slices.
#
# Used by:
#   - save_raw_plane_netcdf
#   - Any workflow that needs physical coordinates for plotting/metadata
def coords_1d(p):
    # Uniform grid (assumed). If you later have staggered grids, adjust.
    x = np.linspace(0.0, p.Lx, p.Nx, endpoint=False, dtype=np.float64)
    y = np.linspace(0.0, p.Ly, p.Ny, endpoint=False, dtype=np.float64)
    z = np.linspace(0.0, p.Lz, p.Nz, endpoint=False, dtype=np.float64)
    return x, y, z

# ---------------------------------------------------------------------
# save_raw_plane_netcdf
# ---------------------------------------------------------------------
# Purpose:
#   Persist raw 2D slices to disk for long-term reuse.
#
# What it does:
#   - Writes u,v,w,r,ee,chi as float32
#   - Stores fixed index (ix/iy/iz) and physical coordinate (x0/y0/z0)
#
# Why it exists:
#   Decouples expensive 3D I/O from downstream plotting and analysis.
#
# Used by:
#   - Export scripts
#   - Long-running interactive sessions
def save_raw_plane_netcdf(
    fields,
    p,
    plane: str,
    idx: int,
    outdir,
    stride=(1, 1, 1),
    fname=None,
    verbose=True,
    stream=True,   # True = write each variable immediately (lower peak RAM)
    progress_cb=None,   # NEW
    varnames=None,   # NEW
):
    """
    Save raw u,v,w,r,ee,chi on one plane to a NetCDF3 classic .nc file.

    - Stores u,v,w,r,ee,chi as float32 ("f4")
    - Stores coords x/y/z as float64 ("f8") (small cost, convenient)
    - Stores fixed plane index (ix/iy/iz) and fixed physical coordinate (x0/y0/z0)
      as length-1 variables over dimension ("one",) to avoid scalar write issues.

    fields: dict of LazyField objects with keys ["u","v","w","r","ee","chi"]
    p: DatParam with Lx,Ly,Lz,Nx,Ny,Nz,dirPath,name,tStamp
    plane: "xy", "xz", or "yz"
    idx: index along the missing axis (z for xy, y for xz, x for yz)
    stride: (sx, sy, sz) sampling stride in x,y,z
    outdir: output folder
    fname: optional filename (default: f"{plane}.nc")
    stream: if True, don't keep all 6 arrays at once
    """
    plane = plane.lower()
    if plane not in {"xy", "xz", "yz"}:
        raise ValueError("plane must be one of {'xy','xz','yz'}")

    outdir = Path(outdir)
    outdir.mkdir(parents=True, exist_ok=True)

    sx, sy, sz = stride
    Nx, Ny, Nz = int(p.Nx), int(p.Ny), int(p.Nz)
    idx = int(idx)

    # --- coords (assumes you have coords_1d(p)) ---
    x, y, z = coords_1d(p)

    # --- figure out 2D grid + fixed axis info ---
    if plane == "xy":
        # fixed z = idx
        if not (0 <= idx < Nz):
            raise IndexError(f"idx={idx} out of bounds for Nz={Nz}")
        x2 = x[::sx]
        y2 = y[::sy]
        dim1_name, dim2_name = "x", "y"
        dim1, dim2 = len(x2), len(y2)
        fixed_name = "iz"
        fixed_coord_name = "z0"
        fixed_coord = float(z[idx])

        coord_payload = {"x": x2, "y": y2}

    elif plane == "xz":
        # fixed y = idx
        if not (0 <= idx < Ny):
            raise IndexError(f"idx={idx} out of bounds for Ny={Ny}")
        x2 = x[::sx]
        z2 = z[::sz]
        dim1_name, dim2_name = "x", "z"
        dim1, dim2 = len(x2), len(z2)
        fixed_name = "iy"
        fixed_coord_name = "y0"
        fixed_coord = float(y[idx])

        coord_payload = {"x": x2, "z": z2}

    else:  # "yz"
        # fixed x = idx
        if not (0 <= idx < Nx):
            raise IndexError(f"idx={idx} out of bounds for Nx={Nx}")
        y2 = y[::sy]
        z2 = z[::sz]
        dim1_name, dim2_name = "y", "z"
        dim1, dim2 = len(y2), len(z2)
        fixed_name = "ix"
        fixed_coord_name = "x0"
        fixed_coord = float(x[idx])

        coord_payload = {"y": y2, "z": z2}

    # file name
    if fname is None:
        fname = f"{plane}.nc"
    path = outdir / fname

    if verbose:
        print(f"\n[save_raw_plane_netcdf] writing {path}", flush=True)
        print(f"  plane={plane} {fixed_name}={idx} stride={stride}", flush=True)
        print(f"  dims: {dim1_name}={dim1}, {dim2_name}={dim2}", flush=True)

    # --- write NetCDF3 ---
    nc = netcdf_file(path, mode="w")
    try:
        # dimensions
        nc.createDimension(dim1_name, dim1)
        nc.createDimension(dim2_name, dim2)
        nc.createDimension("one", 1)

        # coordinate variables
        for cname, cvals in coord_payload.items():
            v = nc.createVariable(cname, "f8", (cname,))
            v[:] = cvals

        # fixed index and fixed coordinate (as length-1 vars)
        vfixed_i = nc.createVariable(fixed_name, "i4", ("one",))
        vfixed_i[0] = idx

        vfixed_x = nc.createVariable(fixed_coord_name, "f8", ("one",))
        vfixed_x[0] = fixed_coord

        # data variables
        # varnames = ["u", "v", "w", "r", "ee", "chi"]
            # data variables
        if varnames is None:
            varnames = ["u", "v", "w", "r", "ee", "chi"]
        else:
            varnames = [str(v) for v in varnames]
    
        # optional sanity check
        missing = [v for v in varnames if v not in fields]
        if missing:
            raise KeyError(f"Missing fields for variables: {missing}. Available: {list(fields.keys())}")
        
        if stream:
            # create vars first
            for name in varnames:
                nc.createVariable(name, "f4", (dim1_name, dim2_name))
        
            n = len(varnames)
            for i, name in enumerate(varnames, start=1):
                A = fields[name].slice2d(
                    plane=plane,
                    idx=idx,
                    stride=stride,
                )
                nc.variables[name][:] = np.asarray(A, dtype=np.float32)
                del A
        
                if progress_cb is not None:
                    progress_cb(var=name, i=i, n=n)
        
        else:
            # load all then write (simple, but higher peak RAM)
            data = {}
            for name in varnames:
                if verbose:
                    print(f"  reading {name} ...", flush=True)
                A = fields[name].slice2d(plane=plane, idx=idx, stride=stride)
                data[name] = np.asarray(A, dtype=np.float32)
        
            for name in varnames:
                if verbose:
                    print(f"  writing {name} ...", flush=True)
                v = nc.createVariable(name, "f4", (dim1_name, dim2_name))
                v[:] = data[name]
        
            data.clear()

        # global attrs
        nc.plane = plane
        nc.case = str(p.name)
        nc.tStamp = str(p.tStamp)
        nc.dirPath = str(p.dirPath)

        nc.Nx, nc.Ny, nc.Nz = Nx, Ny, Nz
        nc.Lx, nc.Ly, nc.Lz = float(p.Lx), float(p.Ly), float(p.Lz)
        nc.stride_x, nc.stride_y, nc.stride_z = int(sx), int(sy), int(sz)
        setattr(nc, fixed_name, int(idx))
    finally:
        nc.close()

    if verbose:
        print("  done.", flush=True)

    return path

# ---------------------------------------------------------------------
# read_raw_plane_netcdf / _read_plane_nc
# ---------------------------------------------------------------------
# Purpose:
#   Reload previously saved 2D slices.
#
# Why they exist:
#   Allow restarting analysis without touching the original 3D data.
#
# Used by:
#   - NetCDF-based plotting notebooks
def read_raw_plane_netcdf(path, copy=True, varnames=None):
    nc = netcdf_file(str(path), "r", mmap=False)
    try:
        if varnames is None:
            # read all float variables except coords + metadata
            skip = {"x","y","z","x0","y0","z0","ix","iy","iz"}
            varnames = [k for k in nc.variables.keys() if k not in skip]

        raw = {}
        for name in varnames:
            if name not in nc.variables:
                continue
            A = nc.variables[name][:]
            raw[name] = np.array(A, dtype=np.float32, copy=copy)

        attrs = dict(nc.__dict__)
    finally:
        nc.close()
    return raw, attrs

def _read_plane_nc(path, varnames=None):
    nc = netcdf_file(str(path), "r", mmap=False)
    try:
        if varnames is None:
            skip = {"x","y","z","x0","y0","z0","ix","iy","iz","one"}
            varnames = [k for k in nc.variables.keys() if k not in skip]

        data = {}
        for name in varnames:
            if name in nc.variables:
                data[name] = np.array(nc.variables[name][:], dtype=np.float32)

        meta = {"attrs": {}}
        for k in ["plane","case","tStamp","Nx","Ny","Nz","Lx","Ly","Lz",
                  "stride_x","stride_y","stride_z","ix","iy","iz"]:
            if hasattr(nc, k):
                meta["attrs"][k] = getattr(nc, k)

        for cname in ["x","y","z","x0","y0","z0"]:
            if cname in nc.variables:
                meta[cname] = np.array(nc.variables[cname][:], dtype=np.float64)

        return data, meta
    finally:
        nc.close()

# ---------------------------------------------------------------------
# plane_stats
# ---------------------------------------------------------------------
# Purpose:
#   Estimate mean energies and dissipation from a single 2D slice.
#
# Why it exists:
#   Lightweight consistency checks against target Ek, Ep.
#
# Used by:
#   - Sanity checks in NetCDF workflows
def plane_stats(raw, p):
    """
    Plane-mean estimates from ONE 2D slice.
    """
    u = raw["u"].astype(np.float64, copy=False)
    v = raw["v"].astype(np.float64, copy=False)
    w = raw["w"].astype(np.float64, copy=False)
    r = raw["r"].astype(np.float64, copy=False)
    ee  = raw["ee"].astype(np.float64, copy=False)
    chi = raw["chi"].astype(np.float64, copy=False)

    Ek = 0.5 * np.mean(u*u + v*v + w*w)
    Ep = np.mean(r*r) * (p.zAccel**2) / (2.0 * p.N2)

    eps_avg = float(np.mean(ee))
    chi_avg = float(np.mean(chi))
    return dict(Ek=float(Ek), Ep=float(Ep), eps_avg=eps_avg, chi_avg=chi_avg)
