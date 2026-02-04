import numpy as np

class DatParam:
    
    def __init__(self, Lx, Ly, Lz, Nx, Ny, Nz, kinV, dGrad, zAccel, targKE, dirPath, name, tStamp, Pr, dRef, dUdz):
        self.Lx = Lx
        self.Ly = Ly
        self.Lz = Lz
        self.Nx = Nx
        self.Ny = Ny
        self.Nz = Nz
        self.kinV = kinV
        self.dGrad = dGrad
        self.zAccel = zAccel
        self.targKE = targKE
        self.dirPath = dirPath
        self.name = name
        self.tStamp = tStamp
        self.Pr = Pr
        self.dRef = dRef
        self.dUdz = dUdz

def generate(): # Initialize classes for each dataset
    
    ## Pr=1
    R1P1 = DatParam(Lx=4*2*np.pi, Ly=2*2*np.pi, Lz=2*np.pi, Nx=1536, Ny=768, Nz=384, kinV=0.000498184, dGrad=-0.001, zAccel=1.64e+02, targKE=0.0157914, dirPath="/lustre/orion/cfd135/proj-shared/Hsst/R1P1/001_Final/",name="R1P1", tStamp="1100.000000", Pr=1, dRef=1, dUdz=1)

    R4P1 = DatParam(Lx=4*2*np.pi, Ly=2*2*np.pi, Lz=2*np.pi, Nx=2048, Ny=1024, Nz=512, kinV=0.000250061, dGrad=-0.001, zAccel=1.5967885147497108e+02, targKE=0.0157914, dirPath="/lustre/orion/cfd135/proj-shared/Hsst/R4P1/001_Final/",name="R4P1", tStamp="270.006053", Pr=1, dRef=1, dUdz=1)

    R6P1 = DatParam(Lx=4*2*np.pi, Ly=2*2*np.pi, Lz=2*np.pi, Nx=3072, Ny=1536, Nz=768, kinV=0.000125138, dGrad=-0.001, zAccel=1.524920e+02, targKE=0.0157914, dirPath="/lustre/orion/cfd135/proj-shared/Hsst/R6P1/001_Final/",name="R6P1", tStamp="96.533028", Pr=1, dRef=1, dUdz=1)

    R8P1 = DatParam(Lx=4*2*np.pi, Ly=2*2*np.pi, Lz=2*np.pi, Nx=8736, Ny=4368, Nz=2184, kinV=0.0000314333, dGrad=-0.001, zAccel=1.5e+02, targKE=0.0157914, dirPath="/lustre/orion/cfd135/proj-shared/Hsst/R8P1/001_Final/",name="R8P1", tStamp="95.780500", Pr=1, dRef=1, dUdz=1)

    R10P1 = DatParam(Lx=4*2*np.pi, Ly=2*2*np.pi, Lz=2*np.pi, Nx=12288, Ny=6144, Nz=3072, kinV=0.0000198331, dGrad=-0.001, zAccel=1.5967885147497108e+02, targKE=0.0157914, dirPath="/lustre/orion/cfd135/proj-shared/Hsst/R10P1/001_Final/",name="R10P1", tStamp="198.101596", Pr=1, dRef=1, dUdz=1)


    ## Pr=7

    R1P7 = DatParam(Lx=4*2*np.pi, Ly=2*2*np.pi, Lz=2*np.pi, Nx=3072, Ny=1536, Nz=768, kinV=0.000498184, dGrad=-0.001, zAccel=1.534170e+02, targKE=0.0157914, dirPath="/lustre/orion/cfd135/proj-shared/Hsst/R1P7/001_Final/",name="R1P7", tStamp="28.989493", Pr=7, dRef=1, dUdz=1)

    R4P7 = DatParam(Lx=4*2*np.pi, Ly=2*2*np.pi, Lz=2*np.pi, Nx=5120, Ny=2560, Nz=1280, kinV=0.000250061, dGrad=-0.001, zAccel=1.533112e+02, targKE=0.0157914, dirPath="/lustre/orion/cfd135/proj-shared/Hsst/R4P7/001_Final/",name="R4P7", tStamp="161.636386", Pr=7, dRef=1, dUdz=1)

    R6P7 = DatParam(Lx=4*2*np.pi, Ly=2*2*np.pi, Lz=2*np.pi, Nx=12288, Ny=6144, Nz=3072, kinV=0.000125138, dGrad=-0.001, zAccel=1.524920e+02, targKE=0.0157914, dirPath="/lustre/orion/cfd135/proj-shared/Hsst/R6P7/001_Final/",name="R6P7", tStamp="55.809401", Pr=7, dRef=1, dUdz=1)

    R8P7 = DatParam(Lx=4*2*np.pi, Ly=2*2*np.pi, Lz=2*np.pi, Nx=23040, Ny=11520, Nz=5760, kinV=0.0000314333, dGrad=-0.001, zAccel=1.5967885147497108e+02, targKE=0.0157914, dirPath="/lustre/orion/cfd135/proj-shared/Hsst/R8P7/001_Final/",name="R8P7", tStamp="58.385090", Pr=7, dRef=1, dUdz=1)

    
    R10P7 = DatParam(Lx=4*2*np.pi, Ly=2*2*np.pi, Lz=2*np.pi, Nx=31680, Ny=15840, Nz=7920, kinV=0.0000198331, dGrad=-0.001, zAccel=1.5967885147497108e+02, targKE=0.0157914, dirPath="/lustre/orion/cfd135/proj-shared/Hsst/R10P7/001_Final/",name="R10P7", tStamp="48.210113", Pr=7, dRef=1, dUdz=1)



    ## Pr=50

    R1P50 = DatParam(Lx=4*2*np.pi, Ly=2*2*np.pi, Lz=2*np.pi, Nx=8000, Ny=4000, Nz=2000, kinV=0.000250061/2.0, dGrad=-0.001, zAccel=1.670898e+02, targKE=0.0157914, dirPath="/lustre/orion/cfd135/proj-shared/Hsst/R1P50/001_Final/",name="R1P50",tStamp="56.563117", Pr=50, dRef=1, dUdz=1)

    R4P50 = DatParam(Lx=4*2*np.pi, Ly=2*2*np.pi, Lz=2*np.pi, Nx=8192, Ny=4096, Nz=2048, kinV=0.000250061, dGrad=-0.001, zAccel=1.670898e+02, targKE=0.0157914, dirPath="/lustre/orion/cfd135/proj-shared/Hsst/R4P50/001_Final/",name="R4P50",tStamp="117.315250", Pr=50, dRef=1, dUdz=1)

    R6P50 = DatParam(Lx=4*2*np.pi, Ly=2*2*np.pi, Lz=2*np.pi, Nx=24000, Ny=12000, Nz=6000, kinV=0.000250061/2.0, dGrad=-0.001, zAccel=1.186733e+02, targKE=0.0157914, dirPath="/lustre/orion/cfd135/proj-shared/Hsst/R6P50/001_Final/",name="R6P50",tStamp="51.658601",Pr=50, dRef=1, dUdz=1)

## CHECK: Something a bit weird with this global file
     #R6P50

     #R8P50
       
    return {'R1P1': R1P1, 'R4P1': R4P1, 'R6P1': R6P1, 'R8P1': R8P1, 'R10P1': R10P1, 'R1P7': R1P7, 'R4P7': R4P7, 'R6P7': R6P7, 'R8P7': R8P7, 'R10P7': R10P7, 'R1P50': R1P50, 'R4P50': R4P50}
