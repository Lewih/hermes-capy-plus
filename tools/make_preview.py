"""Render assets/preview.gif (run / laptop / munch / bird / sign / onsen / cry) from pet/spritesheet.webp.
   uv run --with pillow python tools/make_preview.py"""
import json
from PIL import Image

W, H = 192, 208
im = Image.open("pet/spritesheet.webp").convert("RGBA")
names = json.load(open("pet/pet.json"))["stateRows"]
rows = [names.index(n) for n in ("running-right", "laptop", "munching", "bird", "sign", "onsen", "crying")]
frames = []
for f in range(6):
    canvas = Image.new("RGBA", (W * len(rows), H), (255, 255, 255, 255))
    for i, r in enumerate(rows):
        canvas.alpha_composite(im.crop((f * W, r * H, f * W + W, r * H + H)), (i * W, 0))
    frames.append(canvas.resize((canvas.width * 2 // 3, H * 2 // 3), Image.LANCZOS).convert("P", palette=Image.ADAPTIVE))
frames[0].save("assets/preview.gif", save_all=True, append_images=frames[1:], duration=180, loop=0, disposal=2)
