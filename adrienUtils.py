# utils.py
import numpy as np
import os
from mpl_toolkits.axes_grid1 import make_axes_locatable
import psutil
from pathlib import Path
from datetime import datetime
from tqdm.auto import tqdm
from IPython.display import display

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
    im = ax.imshow(Z.T, origin="lower", cmap=cmap, vmin=vmin, vmax=vmax, aspect="equal")
    divider = make_axes_locatable(ax)
    cax = divider.append_axes("right", size="3.5%", pad=0.08)
    cb = ax.figure.colorbar(im, cax=cax)
    cb.set_label(cbar_label)
    return im, cb


def set_index_axis(ax, axis="x", N=1, label=None, nticks=5):
    ticks = np.linspace(0, N, nticks, dtype=int)
    if axis == "x":
        ax.set_xticks(ticks)
        ax.set_xticklabels([f"{t}" for t in ticks])
        if label:
            ax.set_xlabel(label)
    elif axis == "y":
        ax.set_yticks(ticks)
        ax.set_yticklabels([f"{t}" for t in ticks])
        if label:
            ax.set_ylabel(label)


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
    fname = f"{p.name}_slice_{slice_dir}{idx}_{timestamp}.{fmt}"
    path = Path(outdir) / fname
    fig.savefig(path, dpi=dpi if fmt.lower() in ["png", "jpg", "jpeg"] else None,
                bbox_inches="tight", facecolor="white")
    print(f"Saved -> {path}")
    return path