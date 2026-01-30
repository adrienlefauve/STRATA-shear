# utils.py
import numpy as np
import os
from mpl_toolkits.axes_grid1 import make_axes_locatable
import psutil
from pathlib import Path
from datetime import datetime
import matplotlib.pyplot as plt
from matplotlib import cm, colors

def load_binary(varName, p):
    filePath = p.dirPath + varName + "_" + p.tStamp
    X = np.memmap(filePath, dtype="single", mode="r",
                  shape=(p.Nx+2, p.Ny, p.Nz), order="F")
    return X[:-2, :, :]  # chop off two rows of zeros


def d_periodic_4th(f, dx, axis):
    return (
        -np.roll(f, -2, axis=axis)
        + 8*np.roll(f, -1, axis=axis)
        - 8*np.roll(f,  1, axis=axis)
        + np.roll(f,  2, axis=axis)
    ) / (12.0 * dx)


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


def save_slice_figure(fig, p, slice_dir, idx, outdir="figures", fmt="png", dpi=300):
    Path(outdir).mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    fname = f"{p.name}_all_variables_{slice_dir}{idx}_{timestamp}.{fmt}"
    path = Path(outdir) / fname
    fig.savefig(path, dpi=dpi if fmt.lower() in ["png", "jpg", "jpeg"] else None,
                bbox_inches="tight", facecolor="white")
    #print(f"Saved -> {path}")
    return path


### NEW STUFF 30 Jan 2025

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
        (u / np.sqrt(Ek), "seismic", -5, 5, r"$u'/E_k^{1/2}$", r"$u'$"),
        (v / np.sqrt(Ek), "seismic", -5, 5, r"$v'/E_k^{1/2}$", r"$v'$"),
        (w / np.sqrt(Ek), "seismic", -5, 5, r"$w'/E_k^{1/2}$", r"$w'$"),
        (b / np.sqrt(N2 * Ep), "viridis", -5, 5, r"$b'/(N E_p^{1/2})$", r"$b'$"),
        (np.log10(eps / eps_avg), "magma", -2, 2, r"$\log_{10}(\varepsilon/\langle\varepsilon\rangle)$", r"$\varepsilon$"),
        (np.log10(chi / chi_avg), "hot",  -2, 3, r"$\log_{10}(\chi/\langle\chi\rangle)$", r"$\chi$"),
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


def plot_slices_native_resolution(
    p,
    u, v, w, b, eps, chi,
    Ek, Ep, N2,
    eps_avg, chi_avg,
    plane="xz",
    idx=None,
    outdir="figures",
    prefix=None,
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
        ("u",   _Z(u / np.sqrt(Ek)),                 "seismic", -5,  5),
        ("v",   _Z(v / np.sqrt(Ek)),                 "seismic", -5,  5),
        ("w",   _Z(w / np.sqrt(Ek)),                 "seismic", -5,  5),
        ("b",   _Z(b / np.sqrt(N2 * Ep)),            "viridis", -5,  5),
        ("e", _Z(np.log10(eps / eps_avg)),           "magma",   -2,  2),
        ("c", _Z(np.log10(chi / chi_avg)),          "hot",     -2,  3),
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

from PIL import Image

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