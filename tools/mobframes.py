# Phone intro: render every frame at its own eased angle (no repeated/skipped source frames -> no stutter)
import sys,os,math
sys.path.insert(0,os.path.dirname(__file__))
import render
N=int(sys.argv[1]); k=int(sys.argv[2]); m=int(sys.argv[3]); out=sys.argv[4]
ease=lambda t: 0.5-0.5*math.cos(math.pi*t)
mesh=render.build_mesh()
for i in range(k,N,m):
    fn=os.path.join(out,'r%03d.png'%i)
    if os.path.exists(fn): continue
    th=360.0*ease(i/(N-1))
    render.render(th,1200,780,mesh=mesh).save(fn+'.tmp.png'); os.replace(fn+'.tmp.png',fn)
    print(i,flush=True)
