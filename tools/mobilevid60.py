# compose the eased-angle renders on the dark backdrop -> mob60/m###.png, then encode 60 fps
import numpy as np, glob, os
from PIL import Image
W,H=1080,780
BG=np.array([0x13,0x12,0x1b],float)
yy,xx=np.mgrid[0:H,0:W]
g=np.exp(-(((xx-W/2)/(W*0.42))**2+((yy-H*0.62)/(H*0.30))**2))
bg=(BG[None,None]+g[...,None]*np.array([16,15,26])[None,None]).astype(np.uint8)
def comp(fn):
    a=np.asarray(Image.open(fn).convert('RGBA'))[:,60:1140].astype(float)
    rgb=a[...,:3]; al=a[...,3:4]/255
    lum=rgb.mean(-1,keepdims=True)
    al=np.where((lum<90)&(al<0.6),al*0.25,al)          # same ground-shadow treatment as before
    return Image.fromarray((bg*(1-al)+rgb*al).round().clip(0,255).astype(np.uint8),'RGB')
fs=sorted(glob.glob('mob60/r*.png')); assert len(fs)==480, len(fs)
for i,f in enumerate(fs): comp(f).save('mob60/m%03d.png'%i)
comp(fs[0]).save('mob60/poster.png')
