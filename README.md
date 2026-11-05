# 310 Meadowcrest
Concept site for 310 Meadowcrest Dr. Static HTML, deployed on Vercel.

- `index.html` – the site (desktop scroll-to-rotate, mobile dark intro + 3D model)
- `assets/frames` – 120 massing frames (desktop)
- `assets/mobile` – mobile intro video, poster, 3D model (.glb)
- `model/` – OBJ + Blender script
- `tools/` – scripts that build the model and render the frames from the architect drawings

Phone intro: `python3 tools/mobframes.py 480 0 1 mob60` renders every frame at its own eased angle, then `python3 tools/mobilevid60.py` composes them and ffmpeg encodes 60 fps (see the 515 Cap Rock repo for the exact command).
