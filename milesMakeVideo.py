import paramClassSheared
import numpy as np
import matplotlib.pyplot as plt
import plotly.graph_objects as go
from joblib import Parallel, delayed

pList = adrienParamClassSheared.generate()

def load_binary(varName,p):
    filePath = p.dirPath + "/001_Final/" + varName + "_" + p.tStamp
    X = np.memmap(filePath, dtype="single", mode="r",shape=(p.Nx+2,p.Ny,p.Nz), order="F")
    return X[:-2,:,:] #Chop off two rows of zeros


def plotSlice(p, sp, xSt):
    
    r = load_binary("r",p)
    
    datacube = r[::sp,::sp,::sp]
    x = np.linspace(0,1,p.Nx//sp)
    y = np.linspace(0,1/2,p.Ny//sp)
    z = np.linspace(0,1/4,p.Nz//sp)

    #Colormap limits
    cmin = -0.001/2
    cmax = -cmin

    X, Y, Z = np.meshgrid(x,y,z, indexing='ij')

    #Idx for z slice
    topIdx = int(0.7*p.Nz/sp);

    dataTop = np.array(datacube[:,:,topIdx])
    dataRight = np.array(datacube[:,1,:])

    p.Nx//sp
    
    fig = go.Figure()
    
    #Top
    fig.add_trace(go.Surface(x=X[xSt:,:,topIdx], y=Y[xSt:,:,topIdx], z=Z[xSt:,:,topIdx], surfacecolor=dataTop[xSt:,:],
                             colorscale='RdBu', showscale=False, cmin=cmin, cmax=cmax))
    #Left front
    fig.add_trace(go.Surface(x=X[xSt,:,:topIdx], y=Y[xSt,:,:topIdx], z=Z[xSt,:,:topIdx], surfacecolor=datacube[xSt,:,:],
                             colorscale='RdBu', showscale=False, cmin=cmin, cmax=cmax))

    #Right front
    fig.add_trace(go.Surface(x=X[xSt:,1,:topIdx], y=Y[xSt:,1,:topIdx], z=Z[xSt:,1,:topIdx], surfacecolor=dataRight[xSt:,:],
                             colorscale='RdBu', showscale=False, cmin=cmin, cmax=cmax))


    fig.update_layout(width=1000, height=600)


    fig.update_layout(
        width = 2500,
        height = 2500*9/16,
        margin=dict(l=0, r=0, b=0, t=0),
        scene=dict(
            aspectmode='manual',
            aspectratio=dict(x=1, y=1/2, z=1/4),
            xaxis=dict(
                visible=False,
                showspikes=False,
                range=[x[0], x[-1]]  # full x range, even if you slice
            ),
            yaxis=dict(
                visible=False,
                showspikes=False,
                range=[y[0], y[-1]]  # y-axis in plot = z in data
            ),
            zaxis=dict(
                visible=False,
                showspikes=False,
                range=[z[0], z[-1]]  # z-axis in plot = y in data
            ),
            camera=dict(
                eye=dict(x=-1, y=-1, z=0.7),
                center=dict(x=0, y=0, z=-0.2)
            )
        )
    )

    # Get domain bounds (from full data)
    x0, x1 = x[0], x[-1]
    y0, y1 = y[0], y[-1]
    z0, z1 = z[0], z[-1]

    # Define the 12 edges of the box
    lines = [
        # Bottom face
        ([x0, x1], [y0, y0], [z0, z0]),
        ([x1, x1], [y0, y0], [z0, z1]),
        ([x1, x0], [y0, y0], [z1, z1] ),
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
        ([x0, x0], [y0, y1], [z1, z1])
    ]

    # Add each line as a trace
    for xi, yi, zi in lines:
        fig.add_trace(go.Scatter3d(
            x=xi, y=yi, z=zi,
            mode='lines',
            line=dict(color='black', width=6),
            showlegend=False
        ))


    fig.show()

    fig.write_image(f"./Figs/R10P7/slice_{xSt:04d}.png", width=2500, height=2500*9/16, scale=1)


p = pList["R10P7"]
sp = 30 #Sparse factor
Parallel(n_jobs=16)(delayed(plotSlice)(p,sp,xSt) for xSt in np.arange(0,(p.Nx//sp)-1,int((p.Nx//sp)/50)))




