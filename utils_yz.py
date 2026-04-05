# utils_yz.py
# A. Lefauve, 2026
#
# Standalone yz-slice reader for large Fortran-order DNS binary files.
#
# WHY THIS EXISTS (and why it is separate from utils.py)
# -------------------------------------------------------
# The binary files produced by the solver are Fortran-order float32 arrays
# with shape (Nx+2, Ny, Nz).  In this layout x varies fastest on disk.
#
# A yz slice at fixed x=idx requires touching every (Nx+2)*Ny-th byte in the
# file (~128 KB gaps for Nx=32000).  The naive memmap approach:
#
#   mm[idx, :Ny, :Nz]
#
# issues O(Ny*Nz) = O(100M) random seeks on a ~TB file.  On Lustre this
# causes jobs to stall for 20+ hours without finishing.
#
# FIX: read large contiguous z-slabs  mm[:, :, iz:iz+chunk]  (a single
# sequential Lustre read per slab), extract x=idx in RAM, and accumulate.
# Total I/O is the same (whole file) but is now purely sequential.
#
# This module is intentionally self-contained and does NOT modify utils.py.
# It mirrors the same file-layout assumptions (Nx+2 padding, F-order, float32).

from __future__ import annotations

import time

import numpy as np
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from scipy.io import netcdf_file


# ---------------------------------------------------------------------------
# LazyFieldYZ
# ---------------------------------------------------------------------------

@dataclass
class LazyFieldYZ:
    """
    Read-only lazy accessor for one DNS variable, optimised for yz slices.

    Layout assumptions (identical to utils.LazyField):
      - Raw binary float32, Fortran order
      - Disk shape: (Nx+2, Ny, Nz)
      - The last 2 x-rows are solver padding and are ignored

    Parameters
    ----------
    filepath : str or Path
    shape_file : (Nx+2, Ny, Nz) — disk shape including padding
    yz_chunk_mem_gb : RAM budget (GB) per z-slab.
        Each slab = (Nx+2)*Ny*4 bytes.
        Set to  floor(node_RAM_GB / n_workers) - 2  on the HPC.
    """
    filepath: str
    shape_file: Tuple[int, int, int]   # (Nx+2, Ny, Nz)
    yz_chunk_mem_gb: float = 8.0
    dtype: np.dtype = np.float32

    _mm: Optional[np.memmap] = field(default=None, repr=False)

    def open(self) -> "LazyFieldYZ":
        if self._mm is None:
            self._mm = np.memmap(
                self.filepath,
                dtype=self.dtype,
                mode="r",
                shape=self.shape_file,
                order="F",
            )
        return self

    @property
    def mm(self) -> np.memmap:
        if self._mm is None:
            self.open()
        return self._mm

    @property
    def shape(self) -> Tuple[int, int, int]:
        """Shape excluding the 2 padding x-rows."""
        Nx_file, Ny, Nz = self.shape_file
        return (Nx_file - 2, Ny, Nz)

    # ------------------------------------------------------------------
    # Single yz slice
    # ------------------------------------------------------------------

    def read_yz(
        self,
        x_idx: int,
        stride: Tuple[int, int, int] = (1, 1, 1),
        verbose: bool = False,
        label: str = "",
    ) -> np.ndarray:
        """
        Return a 2D array of shape (Ny_out, Nz_out) for the yz plane at x=x_idx.

        Uses the slab-based sequential reader: reads z-chunks of size
        `yz_chunk_mem_gb` GB each, avoiding random seeks across the file.

        stride : (sx, sy, sz) — sx is unused (x_idx is exact); sy, sz subsample.
        """
        _sx, sy, sz = stride
        Nx_file, Ny, Nz = self.shape_file
        Nx = Nx_file - 2

        if not (0 <= x_idx < Nx):
            raise IndexError(f"x_idx={x_idx} out of bounds [0, {Nx})")

        bytes_per_z = Nx_file * Ny * np.dtype(self.dtype).itemsize
        chunk_nz    = max(1, int(self.yz_chunk_mem_gb * 1024 ** 3) // bytes_per_z)

        Ny_out = len(range(0, Ny, sy))
        Nz_out = len(range(0, Nz, sz))
        result = np.empty((Ny_out, Nz_out), dtype=self.dtype)

        n_slabs = -(-Nz // (sz * chunk_nz))
        _tag = f"[{label}] " if label else ""
        t0 = time.perf_counter()

        iz_out = 0
        for slab_idx, iz0 in enumerate(range(0, Nz, sz * chunk_nz), 1):
            iz1  = min(iz0 + sz * chunk_nz, Nz)
            if verbose:
                elapsed = time.perf_counter() - t0
                eta_str = (f"ETA {elapsed / (slab_idx - 1) * (n_slabs - slab_idx + 1):.0f}s"
                           if slab_idx > 1 else "ETA --")
                print(f"{_tag}slab {slab_idx}/{n_slabs}  z={iz0}..{iz1-1}  "
                      f"elapsed {elapsed:.0f}s  {eta_str}", flush=True)
            slab = np.asarray(self.mm[:Nx_file, :Ny, iz0:iz1])   # contiguous read
            row  = slab[x_idx, ::sy, ::sz]                        # extract in RAM
            n_z  = row.shape[1]
            result[:, iz_out:iz_out + n_z] = row
            iz_out += n_z
            del slab

        if verbose:
            elapsed = time.perf_counter() - t0
            total_gb = Nx_file * Ny * Nz * 4 / 1024 ** 3
            rate_mb  = total_gb * 1024 / elapsed if elapsed > 0 else float("inf")
            print(f"{_tag}read complete  {total_gb:.2f} GB in {elapsed:.0f}s  "
                  f"({rate_mb:.0f} MB/s)", flush=True)

        return result

    # ------------------------------------------------------------------
    # Multiple yz slices in ONE file pass
    # ------------------------------------------------------------------

    def read_yz_multi(
        self,
        x_idxs: List[int],
        stride: Tuple[int, int, int] = (1, 1, 1),
        verbose: bool = False,
        label: str = "",
    ) -> Dict[int, np.ndarray]:
        """
        Extract yz slices at multiple x-indices in a SINGLE sequential pass.

        The file is read exactly once regardless of how many indices are
        requested.  Returns {x_idx: np.ndarray of shape (Ny_out, Nz_out)}.

        stride : (sx, sy, sz) — sx unused; sy, sz subsample y and z.
        """
        x_idxs = [int(i) for i in x_idxs]
        if not x_idxs:
            return {}

        _sx, sy, sz = stride
        Nx_file, Ny, Nz = self.shape_file
        Nx = Nx_file - 2

        for xi in x_idxs:
            if not (0 <= xi < Nx):
                raise IndexError(f"x_idx={xi} out of bounds [0, {Nx})")

        bytes_per_z = Nx_file * Ny * np.dtype(self.dtype).itemsize
        chunk_nz    = max(1, int(self.yz_chunk_mem_gb * 1024 ** 3) // bytes_per_z)

        Ny_out = len(range(0, Ny, sy))
        Nz_out = len(range(0, Nz, sz))
        results = {xi: np.empty((Ny_out, Nz_out), dtype=self.dtype) for xi in x_idxs}

        n_slabs = -(-Nz // (sz * chunk_nz))
        _tag = f"[{label}] " if label else ""
        t0 = time.perf_counter()

        iz_out = 0
        for slab_idx, iz0 in enumerate(range(0, Nz, sz * chunk_nz), 1):
            iz1  = min(iz0 + sz * chunk_nz, Nz)
            if verbose:
                elapsed = time.perf_counter() - t0
                eta_str = (f"ETA {elapsed / (slab_idx - 1) * (n_slabs - slab_idx + 1):.0f}s"
                           if slab_idx > 1 else "ETA --")
                print(f"{_tag}slab {slab_idx}/{n_slabs}  z={iz0}..{iz1-1}  "
                      f"elapsed {elapsed:.0f}s  {eta_str}", flush=True)
            slab = np.asarray(self.mm[:Nx_file, :Ny, iz0:iz1])   # one contiguous read
            slab_nz = slab.shape[2]
            n_z = len(range(0, slab_nz, sz))
            for xi in x_idxs:
                results[xi][:, iz_out:iz_out + n_z] = slab[xi, ::sy, ::sz]
            iz_out += n_z
            del slab

        if verbose:
            elapsed = time.perf_counter() - t0
            total_gb = Nx_file * Ny * Nz * 4 / 1024 ** 3
            rate_mb  = total_gb * 1024 / elapsed if elapsed > 0 else float("inf")
            print(f"{_tag}read complete  {total_gb:.2f} GB in {elapsed:.0f}s  "
                  f"({rate_mb:.0f} MB/s)", flush=True)

        return results


# ---------------------------------------------------------------------------
# Convenience constructors
# ---------------------------------------------------------------------------

def open_lazy_yz(varName: str, p, yz_chunk_mem_gb: float = 8.0) -> LazyFieldYZ:
    """
    Open one variable for yz-optimised reading.

    Parameters
    ----------
    varName : e.g. "u", "v", "r", "ee", "chi"
    p       : case namespace with dirPath, tStamp, Nx, Ny, Nz
    yz_chunk_mem_gb : slab memory budget (GB).
        Rule of thumb: floor(available_node_RAM_GB / n_workers) - 2
        Examples:
          R1P1  (Nx=1536):  slab ≈ 12  MB  →  8 GB default is fine (1 slab)
          R8P7  (Nx=23040): slab ≈ 1.0 GB  →  18 GB budget → ~17 z-planes/slab
          R10P7 (Nx=31680): slab ≈ 1.9 GB  →  28 GB budget → ~14 z-planes/slab
    """
    filepath = p.dirPath + varName + "_" + p.tStamp
    return LazyFieldYZ(
        filepath=filepath,
        shape_file=(p.Nx + 2, p.Ny, p.Nz),
        yz_chunk_mem_gb=yz_chunk_mem_gb,
    ).open()


# ---------------------------------------------------------------------------
# NetCDF writer (mirrors utils.save_raw_plane_netcdf for plane='yz')
# ---------------------------------------------------------------------------

def _coords_1d(p):
    x = np.linspace(0.0, p.Lx, p.Nx, endpoint=False, dtype=np.float64)
    y = np.linspace(0.0, p.Ly, p.Ny, endpoint=False, dtype=np.float64)
    z = np.linspace(0.0, p.Lz, p.Nz, endpoint=False, dtype=np.float64)
    return x, y, z


def write_yz_netcdf(
    arr2d: np.ndarray,
    varname: str,
    p,
    x_idx: int,
    stride: Tuple[int, int, int],
    outdir: Path,
    fname: str,
    overwrite: bool = False,
) -> str:
    """
    Write one yz slice (already in RAM) to a NetCDF3 classic file.

    The output layout matches utils.save_raw_plane_netcdf(plane='yz'):
      dimensions : y, z, one
      variables  : y (f8), z (f8), ix (i4), x0 (f8), <varname> (f4)
      attributes : plane, case, tStamp, Nx/Ny/Nz, Lx/Ly/Lz, stride_*, ix
    """
    path = Path(outdir) / fname
    if path.exists() and not overwrite:
        print(f"[skip] {path.name} exists", flush=True)
        return str(path)

    _sx, sy, sz = stride
    x, y, z = _coords_1d(p)
    y2 = y[::sy]
    z2 = z[::sz]

    nc = netcdf_file(str(path), mode="w")
    try:
        nc.createDimension("y",   len(y2))
        nc.createDimension("z",   len(z2))
        nc.createDimension("one", 1)

        vy = nc.createVariable("y", "f8", ("y",));  vy[:] = y2
        vz = nc.createVariable("z", "f8", ("z",));  vz[:] = z2

        vix = nc.createVariable("ix", "i4", ("one",));  vix[0] = int(x_idx)
        vx0 = nc.createVariable("x0", "f8", ("one",));  vx0[0] = float(x[x_idx])

        vd = nc.createVariable(varname, "f4", ("y", "z"))
        vd[:] = np.asarray(arr2d, dtype=np.float32)

        nc.plane   = "yz"
        nc.case    = str(p.name)
        nc.tStamp  = str(p.tStamp)
        nc.dirPath = str(p.dirPath)
        nc.Nx, nc.Ny, nc.Nz = int(p.Nx), int(p.Ny), int(p.Nz)
        nc.Lx, nc.Ly, nc.Lz = float(p.Lx), float(p.Ly), float(p.Lz)
        nc.stride_x, nc.stride_y, nc.stride_z = 1, int(sy), int(sz)
        nc.ix = int(x_idx)
    finally:
        nc.close()

    return str(path)
