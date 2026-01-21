# adrienParamSpectra.py
import numpy as np
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class SpectraCase:
    name: str
    Nx: int
    Ny: int
    Nz: int

    Pr: float
    Reb: float   # Reb = Gn from Steve's table
    Fr: float

    base_dir: str = "/lustre/orion/cfd135/proj-shared/Hsst"
    spectra_dir: str = "SpectraAdrien"
    default_tstamp: str | None = None
    kmaxLB: float | None = None

    @property
    def case_dir(self) -> Path:
        return Path(self.base_dir) / self.name

    @property
    def spectra_path(self) -> Path:
        return self.case_dir / self.spectra_dir

    def file(self, tstamp: str | None = None, prefix: str = "wwspec_", ext: str = ".nc") -> Path:
        ts = tstamp or self.default_tstamp
        if ts is None:
            raise ValueError(f"No tstamp provided and no default_tstamp set for {self.name}")
        return self.spectra_path / f"{prefix}{ts}{ext}"

    # ---- derived wavenumbers ----
    @property
    def kmin(self) -> float:
        # with Lx = 8π, kmin=1/4
        return 1/4
        
    @property
    def kmax(self) -> float:
        # with Lx = 8π, the stored max k is Nx/8
        return self.Nx / 8

    @property
    def kB(self) -> float:
        # kmaxLB = kmax * LB  ->  LB = kmaxLB / kmax  ->  kB = 2π/LB = 2π * kmax / kmaxLB
        if self.kmaxLB is None:
            raise ValueError(f"kmaxLB not set for {self.name}")
        return (2 * np.pi / self.kmaxLB) * self.kmax

    @property
    def kK(self) -> float:
        # kK = kB / sqrt(Pr)
        return self.kB / (self.Pr ** 0.5)

    @property
    def kO(self) -> float:
        # kO = kK / Reb^(3/4)
        return self.kK / (self.Reb ** (3 / 4))

    @property
    def kL(self) -> float:
        # kL = kO * Fr^(3/2)
        return self.kO * (self.Fr ** (3 / 2))


# ---- registry (edit/extend here) ----
# Columns used: Fr, Gn->Reb, kmaxLB, Nx Ny Nz, and default_tstamp from Miles' param list
CASES: dict[str, SpectraCase] = {
    # Pr = 1
    "R1P1":  SpectraCase("R1P1",  Nx=1536,  Ny=768,   Nz=384,  Pr=1,  Reb=34.7,  Fr=0.442,
                        default_tstamp="1100.000000", kmaxLB=2.78),
    "R4P1":  SpectraCase("R4P1",  Nx=2048,  Ny=1024,  Nz=512,  Pr=1,  Reb=81.1,  Fr=0.503,
                        default_tstamp="270.006053",  kmaxLB=2.16),
    "R6P1":  SpectraCase("R6P1",  Nx=3200,  Ny=1600,  Nz=800,  Pr=1,  Reb=218.0, Fr=0.601,
                        default_tstamp="96.533028",   kmaxLB=1.97),
    "R8P1":  SpectraCase("R8P1",  Nx=7168,  Ny=3584,  Nz=1792, Pr=1,  Reb=519.0, Fr=0.397,
                        default_tstamp="94.749000",   kmaxLB=2.07),
    "R10P1": SpectraCase("R10P1", Nx=12288, Ny=6144,  Nz=3072, Pr=1,  Reb=1009.0,Fr=0.460,
                        default_tstamp="256.000000",  kmaxLB=2.01),

    # Pr = 7
    "R1P7":  SpectraCase("R1P7",  Nx=12288, Ny=6144,  Nz=3072, Pr=7,  Reb=33.9,  Fr=0.440,
                        default_tstamp="28.989493",   kmaxLB=8.37),
    "R4P7":  SpectraCase("R4P7",  Nx=12288, Ny=6144,  Nz=3072, Pr=7,  Reb=83.0,  Fr=0.514,
                        default_tstamp="161.636386",  kmaxLB=2.03),
    "R6P7":  SpectraCase("R6P7",  Nx=8800,  Ny=4400,  Nz=2200, Pr=7,  Reb=202.0, Fr=0.571,
                        default_tstamp="55.809401",   kmaxLB=2.88),
    "R8P7":  SpectraCase("R8P7",  Nx=23040, Ny=11520, Nz=5760, Pr=7,  Reb=567.0, Fr=0.434,
                        default_tstamp="58.385090",   kmaxLB=2.02),
    "R10P7": SpectraCase("R10P7", Nx=31680, Ny=15840, Nz=7920, Pr=7,  Reb=838.0, Fr=0.407,
                        default_tstamp="48.210113",   kmaxLB=1.99),

    # Pr = 50
    "R1P50": SpectraCase("R1P50", Nx=8000,  Ny=4000,  Nz=2000, Pr=50, Reb=35.5,  Fr=0.456,
                        default_tstamp="56.563117",   kmaxLB=2.03),
    "R4P50": SpectraCase("R4P50", Nx=8192,  Ny=4096,  Nz=2048, Pr=50, Reb=83.9,  Fr=0.519,
                        default_tstamp="117.315250",  kmaxLB=2.36),
    "R6P50": SpectraCase("R6P50", Nx=24000, Ny=12000, Nz=6000, Pr=50, Reb=216.0, Fr=0.599,
                        default_tstamp="51.658601",   kmaxLB=2.10),
}


def get(case: str) -> SpectraCase:
    return CASES[case]