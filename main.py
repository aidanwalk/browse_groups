# bokeh_image_browser.py
# Requires: bokeh, numpy, astropy
# Run with: bokeh serve browse_groups.py --show

import numpy as np
from astropy.io import fits
import argparse
import sys



from bokeh.io import curdoc
from bokeh.layouts import column
from bokeh.models import Slider, Div, ColumnDataSource
from bokeh.plotting import figure
from bokeh.palettes import Greys256
from bokeh.transform import linear_cmap





# ─── Load data ────────────────────────────────────────────────────────
# add argument for input fits file and membership file from terminal (not optional)
parser = argparse.ArgumentParser(description="Browse grouped FITS frames with Bokeh")
parser.add_argument('-f', '--fits', type=str, default='prepped_images.fits', help='Path to the FITS file containing the frames')
parser.add_argument('-m', '--membership', type=str, default='./prepped_images.clusterdat/frame_membership.txt', help='Path to the frame membership file')
args = parser.parse_args()  



fits_file = args.fits
membership_file = args.membership

dat = fits.getdata(fits_file)                     # shape: (n_frames, height, width)
frame_membership = np.genfromtxt(membership_file, dtype=int)  # Nx2: [frame_idx, group_idx]

# Build list of lists: groups[g] = list of frame indices in that group
max_group = frame_membership[:,1].max()
groups = [[] for _ in range(max_group + 1)]

for frame_idx, group_idx in frame_membership:
    groups[group_idx].append(frame_idx)

# Remove empty groups (if any) and re-index for clean 0…n_groups-1
groups = [g for g in groups if g]
n_groups = len(groups)

# Order groups by size (optional), but keep track of original group indices if needed
group_indices = list(range(n_groups))
group_indices.sort(key=lambda i: len(groups[i]), reverse=True)
groups = [groups[i] for i in group_indices]
# groups.sort(key=len, reverse=True)

# Precompute min/max for consistent colormap
dat -= np.nanmin(dat, axis=(1,2))[:, None, None]  # shift to non-negative
# dat /= np.nanmax(dat, axis=(1,2)).astype(np.uint16)[:, None, None]  # scale to [0,1]
# dat = np.log10(dat)  # log scale for better contrast (adjust as needed)
vmin = np.percentile(dat, 1) 
vmax = np.percentile(dat, 99)
print(np.nanmax(dat), np.nanmin(dat), np.shape(np.nanmax(dat, axis=(1,2))))

print(f"Loaded {dat.shape[0]} frames in {n_groups} groups")
print(f"Intensity range: {vmin:.2f} – {vmax:.2f}")

# ─── Bokeh setup ────────────────────────────────────────────────────────────
p = figure(
    title="Vampires PSF",
    tools="wheel_zoom,pan,reset,save",
    toolbar_location="right",
    sizing_mode="scale_width",
    # aspect_ratio=dat.shape[2]/dat.shape[1],   # preserve image aspect
    x_range=(0, dat.shape[2]),
    y_range=(0, dat.shape[1]),
    output_backend="webgl"   # better for large images
)

# Initial image (first frame of first group)
init_frame_idx = groups[0][0]
dw, dh = dat.shape[2], dat.shape[1]
# dw = 500
# dh = 500
img_source = ColumnDataSource(data=dict(
    image=[dat[init_frame_idx]],
    x=[0], y=[0], dw=[dw], dh=[dh]
))

# Use Greys256 palette (you can change to 'Viridis256', 'Magma256', etc.)
mapper = linear_cmap(
    field_name='image',
    palette=Greys256,
    low=vmin,
    high=vmax,
    nan_color="black"
)

im = p.image(
    image='image', x='x', y='y', dw='dw', dh='dh',
    source=img_source,
    color_mapper=mapper['transform'],
    level="image"
)

p.axis.visible = False
p.grid.visible = False
p.outline_line_color = None

# ─── Widgets ────────────────────────────────────────────────────────────────
group_slider = Slider(
    title="Group",
    start=0,
    end=n_groups - 1,
    value=0,
    step=1,
    width=400
)

frame_slider = Slider(
    title="Frame in group",
    start=0,
    end=len(groups[0]) - 1,
    value=0,
    step=1,
    width=400
)

title_div = Div(
    text=f"<b>Global frame:</b> {init_frame_idx} &nbsp;&nbsp; <b>Group:</b> 0 &nbsp;&nbsp; <b>Local index:</b> 0 &nbsp;&nbsp; <b>Group size:</b> 0 &nbsp;&nbsp;",
    width=500,
    styles={'font-size': '110%'}
)

# ─── Update logic ───────────────────────────────────────────────────────────
def update_image(attr, old, new):
    g = group_slider.value
    f_local = frame_slider.value
    
    if g >= len(groups) or f_local >= len(groups[g]):
        return  # safety
    
    frame_idx = groups[g][f_local]
    group_idx = group_indices[g]  # if you want to show original group index instead of sorted one
    
    # Update image data
    img_source.data = dict(
        image=[dat[frame_idx]],
        x=[0], y=[0],
        dw=[dw], dh=[dh]
    )
    
    # Update title and info
    # p.title.text = f"Group {g} • Local frame {f_local}  (global idx {frame_idx})"
    title_div.text = (
        f"<b>Global frame:</b> {frame_idx} &nbsp;&nbsp; "
        f"<b>Group:</b> {group_idx} &nbsp;&nbsp; "
        f"<b>Local index:</b> {f_local} &nbsp;&nbsp;"
        f"<b>Group size:</b> {len(groups[g])}"
    )

# ─── Link sliders ───────────────────────────────────────────────────────────
def update_frame_range(attr, old, new):
    g = new  # new group index
    n_frames_in_group = len(groups[g])
    frame_slider.end = n_frames_in_group - 1
    # If current local frame is out of range → reset to 0
    if frame_slider.value >= n_frames_in_group:
        frame_slider.value = 0

group_slider.on_change('value', update_frame_range)
group_slider.on_change('value', update_image)
frame_slider.on_change('value', update_image)

# ─── Layout ─────────────────────────────────────────────────────────────────
layout = column(
    title_div,
    group_slider,
    frame_slider,
    p,
    sizing_mode="stretch_both",
    max_width=800
)

curdoc().title = "Grouped FITS Frame Browser"
curdoc().add_root(layout)