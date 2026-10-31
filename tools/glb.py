import sys,os,json,struct
sys.path.insert(0,os.path.dirname(__file__))
import numpy as np
import house, render
FT=0.3048; CX,CY=32.9,34.3
def tf(p): return [(p[0]-CX)*FT, p[2]*FT, -(p[1]-CY)*FT]   # glTF: Y up, front faces +Z
mats=['wall','roof','glass','void']
col={'wall':[0.93,0.92,0.89],'roof':[0.86,0.85,0.83],'glass':[0.62,0.63,0.66],'void':[0.25,0.25,0.27]}
prims={m:{'pos':[],'nrm':[]} for m in mats}
lines=[]; seen=set()
for pts,mat in house.geometry():
    tris,n=render.triangulate(pts)
    N=tf([n[0]+CX,n[1]+CY,n[2]]); N=np.array(N)-np.array(tf([CX,CY,0])); N/=np.linalg.norm(N)
    for t in tris:
        for i in t:
            prims[mat]['pos'].append(tf(pts[i])); prims[mat]['nrm'].append(list(N))
    k=len(pts)
    for i in range(k):
        a=tuple(round(v,3) for v in tf(pts[i])); b=tuple(round(v,3) for v in tf(pts[(i+1)%k]))
        key=tuple(sorted([a,b]))
        if key in seen or a==b: continue
        seen.add(key); lines+= [list(a),list(b)]
buf=bytearray(); views=[]; accs=[]; meshprims=[]; gmats=[]
def add(arr,target=34962):
    arr=np.asarray(arr,np.float32); off=len(buf); buf.extend(arr.tobytes())
    while len(buf)%4: buf.append(0)
    views.append({'buffer':0,'byteOffset':off,'byteLength':arr.nbytes,'target':target})
    accs.append({'bufferView':len(views)-1,'componentType':5126,'count':len(arr),'type':'VEC3',
                 'min':arr.min(0).tolist(),'max':arr.max(0).tolist()})
    return len(accs)-1
for m in mats:
    if not prims[m]['pos']: continue
    gmats.append({'name':m,'pbrMetallicRoughness':{'baseColorFactor':col[m]+[1],'metallicFactor':0,'roughnessFactor':0.92},'doubleSided':True})
    meshprims.append({'attributes':{'POSITION':add(prims[m]['pos']),'NORMAL':add(prims[m]['nrm'])},'material':len(gmats)-1,'mode':4})
gmats.append({'name':'outline','pbrMetallicRoughness':{'baseColorFactor':[0.2,0.2,0.21,1],'metallicFactor':0,'roughnessFactor':1}})
lineprim={'attributes':{'POSITION':add(lines)},'material':len(gmats)-1,'mode':1}
gltf={'asset':{'version':'2.0','generator':'310 Meadowcrest massing'},'scene':0,'scenes':[{'nodes':[0,1]}],
 'nodes':[{'name':'house','mesh':0},{'name':'outlines','mesh':1}],
 'meshes':[{'name':'house','primitives':meshprims},{'name':'outlines','primitives':[lineprim]}],
 'materials':gmats,'buffers':[{'byteLength':len(buf)}],'bufferViews':views,'accessors':accs}
js=json.dumps(gltf,separators=(',',':')).encode()
while len(js)%4: js+=b' '
out=sys.argv[1]
with open(out,'wb') as f:
    total=12+8+len(js)+8+len(buf)
    f.write(struct.pack('<III',0x46546C67,2,total))
    f.write(struct.pack('<II',len(js),0x4E4F534A)); f.write(js)
    f.write(struct.pack('<II',len(buf),0x004E4942)); f.write(buf)
print(out, total, 'bytes', len(lines)//2, 'edges')
