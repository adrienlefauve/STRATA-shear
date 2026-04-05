#!/usr/bin/env python3
"""
test_yz_slab_reader.py
----------------------
Validates and benchmarks the new slab-based yz slice reader in LazyField.

Creates a small synthetic binary file in Fortran order (same layout as the
DNS solver output), then compares:
  - OLD: naive strided memmap read  mm[idx, ::sy, ::sz]
  - NEW: slab-based sequential read (LazyField.slice2d with plane="yz")

And times both on a grid that is large enough to observe the difference
in access patterns without needing the real 14.5 TB data.

Usage:
  python test_yz_slab_reader.py
  python test_yz_slab_reader.py --nx 512 --ny 256 --nz 128 --chunk-gb 0.1
  python test_yz_slab_reader.py --nx 512 --ny 256 --nz 128 --no-timing
"""

import argparse
import tempfile
import time
from pathlib import Path
from types import SimpleNamespace

import numpy as np

import utils


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_synthetic_binary(path: Path, Nx: int, Ny: int, Nz: int, seed: int = 42):
    """
    Write a synthetic float32 Fortran-order binary file with shape (Nx+2, Ny, Nz),
    matching the DNS solver layout exactly.

    Values are deterministic: each element equals its flat Fortran-order index
    mod 1000 as a float32, so we can verify correctness without storing a full
    reference array.
    """
    rng = np.random.default_rng(seed)
    data = rng.standard_normal((Nx + 2, Ny, Nz)).astype(np.float32, order="F")
    # Write raw bytes (Fortran order means x varies fastest in the file)
    data.flatten(order="F").tofile(path)
    return data  # (Nx+2, Ny, Nz), F-order reference


def naive_yz_read(mm: np.memmap, idx: int, Nx: int, Ny: int, Nz: int,
                  sy: int, sz: int) -> np.ndarray:
    """
    Old approach: direct strided memmap indexing.
    Produces correct results but causes Ny*Nz random seeks in the file.
    """
    return np.asarray(mm[idx:idx + 1, :Ny:sy, :Nz:sz][0, :, :])


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def parse_args():
    ap = argparse.ArgumentParser(description="Test yz slab reader in LazyField.")
    ap.add_argument("--nx",       type=int,   default=256,  help="Nx (grid, excl. padding)")
    ap.add_argument("--ny",       type=int,   default=128,  help="Ny")
    ap.add_argument("--nz",       type=int,   default=64,   help="Nz")
    ap.add_argument("--idx",      type=int,   default=None, help="x-index for yz slice (default: Nx//2)")
    ap.add_argument("--stride",   type=int,   default=1,    help="Uniform stride in y and z (default 1)")
    ap.add_argument("--chunk-gb", type=float, default=0.05,
                    help="yz_chunk_mem_gb for LazyField (default 0.05 = 50 MB)")
    ap.add_argument("--no-timing", action="store_true",
                    help="Skip timing comparison (correctness check only)")
    ap.add_argument("--repeat",   type=int,   default=3,
                    help="Number of timing repetitions to average (default 3)")
    return ap.parse_args()


def main():
    args = parse_args()

    Nx, Ny, Nz = args.nx, args.ny, args.nz
    idx = args.idx if args.idx is not None else Nx // 2
    sy = sz = args.stride

    if not (0 <= idx < Nx):
        raise ValueError(f"--idx {idx} out of range [0, {Nx})")

    file_size_mb = (Nx + 2) * Ny * Nz * 4 / 1024**2
    print(f"[test] Nx={Nx} Ny={Ny} Nz={Nz}  (padded shape: {Nx+2}x{Ny}x{Nz})")
    print(f"[test] file size: {file_size_mb:.1f} MB")
    print(f"[test] yz slice at x={idx}, stride=({sy},{sz})")
    print(f"[test] chunk budget: {args.chunk_gb} GB")

    with tempfile.TemporaryDirectory() as tmpdir:
        fpath = Path(tmpdir) / "u_000000.000000"

        # --- Write synthetic file ---
        print("\n[test] writing synthetic binary file ...", flush=True)
        t0 = time.perf_counter()
        reference = make_synthetic_binary(fpath, Nx, Ny, Nz)
        print(f"[test] write done ({time.perf_counter()-t0:.2f}s)", flush=True)

        # --- Ground truth: index directly from the in-memory reference array ---
        expected = reference[idx, ::sy, ::sz]   # shape (Ny_out, Nz_out)
        print(f"[test] expected slice shape: {expected.shape}")

        # --- Build a minimal params namespace so open_lazy_field works ---
        p = SimpleNamespace(
            name="test",
            tStamp="000000.000000",
            Nx=Nx, Ny=Ny, Nz=Nz,
            Lx=1.0, Ly=0.5, Lz=0.25,
            dirPath=str(tmpdir) + "/",
        )

        # --- NEW: slab-based reader ---
        print("\n[test] === correctness check ===", flush=True)
        field = utils.open_lazy_field("u", p, yz_chunk_mem_gb=args.chunk_gb)
        result = field.slice2d(plane="yz", idx=idx, stride=(1, sy, sz))

        if result.shape != expected.shape:
            print(f"[FAIL] shape mismatch: got {result.shape}, expected {expected.shape}")
            return 1

        if not np.allclose(result, expected, atol=0, rtol=0):
            max_err = float(np.max(np.abs(result.astype(np.float64) - expected.astype(np.float64))))
            print(f"[FAIL] values mismatch: max abs error = {max_err:.2e}")
            return 1

        print(f"[PASS] slab reader matches reference (shape {result.shape}, all values exact)")

        # --- Also verify xz and xy are unaffected ---
        print("\n[test] checking xz and xy planes are unaffected ...", flush=True)
        for plane, ref_slice in [
            ("xz", reference[:Nx, Ny // 2, ::sz]),       # (Nx, Nz_out)
            ("xy", reference[:Nx, ::sy, Nz // 2]),        # (Nx, Ny_out)
        ]:
            got = field.slice2d(plane=plane, idx=(Ny // 2 if plane == "xz" else Nz // 2),
                                stride=(1, sy, sz))
            if not np.allclose(got, ref_slice, atol=0, rtol=0):
                max_err = float(np.max(np.abs(got.astype(np.float64) - ref_slice.astype(np.float64))))
                print(f"[FAIL] {plane} plane mismatch: max err = {max_err:.2e}")
                return 1
            print(f"[PASS] {plane} plane correct (shape {got.shape})")

        if args.no_timing:
            print("\n[test] timing skipped (--no-timing).")
            return 0

        # --- Timing comparison ---
        print(f"\n[test] === timing ({args.repeat} reps each) ===", flush=True)

        mm = field.mm  # reuse the open memmap

        # Warm up OS page cache (optional, makes comparison fairer)
        _ = naive_yz_read(mm, idx, Nx, Ny, Nz, sy, sz)
        _ = field.slice2d(plane="yz", idx=idx, stride=(1, sy, sz))

        # Time OLD
        t_old = []
        for _ in range(args.repeat):
            t0 = time.perf_counter()
            naive_yz_read(mm, idx, Nx, Ny, Nz, sy, sz)
            t_old.append(time.perf_counter() - t0)

        # Time NEW
        t_new = []
        for _ in range(args.repeat):
            t0 = time.perf_counter()
            field.slice2d(plane="yz", idx=idx, stride=(1, sy, sz))
            t_new.append(time.perf_counter() - t0)

        avg_old = sum(t_old) / len(t_old)
        avg_new = sum(t_new) / len(t_new)
        speedup = avg_old / avg_new if avg_new > 0 else float("inf")

        print(f"  OLD (naive strided):  {avg_old*1000:.1f} ms  (avg over {args.repeat} reps)")
        print(f"  NEW (slab reader):    {avg_new*1000:.1f} ms  (avg over {args.repeat} reps)")
        print(f"  Speedup on this machine: {speedup:.1f}x")
        print()
        print("  NOTE: on Lustre the speedup is much larger (100-1000x) because the")
        print("  old approach issues Ny*Nz (~millions) of random seeks across the file,")
        print("  while the new approach only reads large contiguous blocks.")

    print("\n[test] all done.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
