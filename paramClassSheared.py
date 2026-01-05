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
    
    
    R1P1 = DatParam(Lx=4*2*np.pi, Ly=2*2*np.pi, Lz=2*np.pi, Nx=1536, Ny=768, Nz=384, kinV=0.000498184, dGrad=-0.001, zAccel=1.64e+02, targKE=0.0157914, dirPath="/lustre/orion/cfd135/proj-shared/Hsst/R1P1/",name="R1P1", tStamp="1100.000000", Pr=1, dRef=1, dUdz=1)
    
       
    return {'R1P1': R1P1}

