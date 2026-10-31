import numpy as np, math
from PIL import Image
W,H=1080,780
BG=np.array([0x13,0x12,0x1b],float)
# soft glow behind/below house
yy,xx=np.mgrid[0:H,0:W]
g=np.exp(-(((xx-W/2)/(W*0.42))**2+((yy-H*0.62)/(H*0.30))**2))
bg=BG[None,None]+g[...,None]*np.array([16,15,26])[None,None]
bgimg=Image.fromarray(bg.astype(np.uint8),'RGB').convert('RGBA')
def frame(i):
    im=Image.open('frames/frame-%03d.webp'%(i%120)).convert('RGBA')
    im=im.crop((80,0,1520,1040)).resize((W,H),Image.LANCZOS)
    a=np.asarray(im).astype(float)
    # brighten/lift the clay slightly for the dark bg, drop ground shadow (dark alpha far from house)
    rgb=a[...,:3]; al=a[...,3:4]/255
    lum=rgb.mean(-1,keepdims=True)
    shadowish=(lum<90)&(al<0.6)
    al=np.where(shadowish,al*0.25,al)
    out=Image.fromarray(np.dstack([rgb,al*255]).astype(np.uint8),'RGBA')
    b=bgimg.copy(); b.alpha_composite(out); return b.convert('RGB')
N=165
ease=lambda t: 0.5-0.5*math.cos(math.pi*t)
for k in range(N):
    t=k/(N-1); idx=int(round(ease(t)*120))
    frame(idx).save('mob/m%03d.png'%k)
frame(0).save('mob/poster.png')
