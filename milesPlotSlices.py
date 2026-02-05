import paramClassSheared
import numpy as np
import matplotlib.pyplot as plt
import plotly.graph_objects as go
from joblib import Parallel, delayed

pList = paramClassSheared.generate()

def load_binary(varName,p):
    filePath = p.dirPath + "/001_Final/" + varName + "_" + p.tStamp
    X = np.memmap(filePath, dtype="single", mode="r",shape=(p.Nx+2,p.Ny,p.Nz), order="F")
    return X[:-2,:,:] #Chop off two rows of zeros

def plot_slice(sl,name):

    fig = plt.figure(frameon=False)
    fig.set_size_inches(3840/72, 2160/72)  # example for 4K at 72 dpi
    
    ax = plt.Axes(fig, [0., 0., 1., 1.])
    ax.set_axis_off()
    fig.add_axes(ax)
    
    ax.imshow(sl.T, origin="lower", cmap="RdBu", vmin=-0.0005,vmax=0.0005)
    
    plt.savefig("./sliceFigs/" + name + ".png", dpi=72, bbox_inches='tight', transparent=True)


simName = "R10P7"
p = pList[simName]
r = load_binary("r",p)
sp = 6

xySl = r[::sp,::sp,int(p.Nz/2)]
yzSl = r[int(p.Nx/2),::sp,::sp]
xzSl = r[::sp,int(p.Ny/2),::sp]

items = [(simName+"xy_sp"+str(sp), xySl), (simName+"yz_sp"+str(sp), yzSl), (simName+"xz_sp"+str(sp), xzSl)]

Parallel(n_jobs=3)(delayed(plot_slice)(sl, name) for name, sl in items )



