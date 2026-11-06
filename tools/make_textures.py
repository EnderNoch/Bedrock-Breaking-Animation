#!/usr/bin/env python3
"""Build the pack's textures from the vanilla Minecraft client jar.

    python3 tools/make_textures.py path/to/client.jar

Both editions ship the same destroy_stage textures (two greys, 61 and 155, on a transparent
background). They only differ in how the cracks are blended onto the block:

  Java      out = 2 * crack * block   (DST_COLOR, SRC_COLOR blend; grey 128 leaves the block alone)
  Bedrock   out = crack * block       (plain multiply, so every crack pixel darkens the block)

So on Java a crack texture at half the brightness gives exactly the Bedrock result. With
Improved Transparency (order-independent transparency, 26.3+) Java draws destroy_oit_stage
instead, blended as ordinary alpha; there, black at alpha 1 - crack gives the same multiply.

The script also writes the pack icon and the README comparison picture.
"""
import sys
import zipfile
from io import BytesIO
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "pack/assets/minecraft/textures/block"
STAGES = range(10)
TRANSPARENT_ALPHA = 26  # the crumbling shader discards anything below alpha 0.1


def load(jar, name):
    return Image.open(BytesIO(jar.read(f"assets/minecraft/textures/block/{name}.png"))).convert("RGBA")


def is_crack(pixel):
    return pixel[3] >= TRANSPARENT_ALPHA


def half(value):
    return int(value / 2 + 0.5)


def java_stage(src):
    """Same picture, every crack grey halved, so Java's 2x multiply becomes a 1x multiply.

    The empty pixels are grey 128 (neutral under a 2x multiply) instead of vanilla's white, so a
    mipmap that averages them into a crack pixel does not brighten the block."""
    out = Image.new("RGBA", src.size, (128, 128, 128, 1))
    for xy in ((x, y) for y in range(src.height) for x in range(src.width)):
        r, g, b, a = src.getpixel(xy)
        if is_crack((r, g, b, a)):
            out.putpixel(xy, (half(r), half(g), half(b), 255))
    return out


def oit_stage(src):
    """Black at alpha 1 - crack: alpha blending then keeps crack/255 of the block."""
    out = Image.new("RGBA", src.size, (0, 0, 0, 0))
    for xy in ((x, y) for y in range(src.height) for x in range(src.width)):
        r, g, b, a = src.getpixel(xy)
        if is_crack((r, g, b, a)):
            out.putpixel(xy, (0, 0, 0, 255 - round((r + g + b) / 3)))
    return out


def blend(block, crack, java):
    """What the game draws for one block face: Java's 2x multiply or Bedrock's 1x multiply."""
    out = block.copy()
    for xy in ((x, y) for y in range(block.height) for x in range(block.width)):
        c = crack.getpixel(xy)
        if not is_crack(c):
            continue
        k = (2 if java else 1) * c[0] / 255
        out.putpixel(xy, tuple(min(255, round(v * k)) for v in block.getpixel(xy)[:3]) + (255,))
    return out


def big(img, scale):
    return img.resize((img.width * scale, img.height * scale), Image.NEAREST)


def main():
    jar = zipfile.ZipFile(sys.argv[1])
    OUT.mkdir(parents=True, exist_ok=True)
    vanilla = {i: load(jar, f"destroy_stage_{i}") for i in STAGES}
    for i in STAGES:
        oit = load(jar, f"destroy_oit_stage_{i}")
        # The two vanilla sets must draw the same cracks, or the OIT mapping below is wrong.
        assert [is_crack(p) for p in vanilla[i].get_flattened_data()] == [is_crack(p) for p in oit.get_flattened_data()], i
        assert {p[:3] for p in vanilla[i].get_flattened_data() if is_crack(p)} <= {(61, 61, 61), (155, 155, 155)}, i
        java_stage(vanilla[i]).save(OUT / f"destroy_stage_{i}.png", optimize=True)
        oit_stage(vanilla[i]).save(OUT / f"destroy_oit_stage_{i}.png", optimize=True)

    # Icon: stone, well on its way to breaking, the Bedrock way.
    stone = load(jar, "stone")
    big(blend(stone, vanilla[6], java=False), 8).convert("RGB").save(ROOT / "pack/pack.png", optimize=True)
    (ROOT / "icon.png").write_bytes((ROOT / "pack/pack.png").read_bytes())

    # Comparison: rows are blocks, columns are stages 2, 5 and 8, vanilla Java on the left.
    blocks = [load(jar, n) for n in ("stone", "dirt", "sand", "oak_planks")]
    stages = (2, 5, 8)
    tile, gap, middle = 96, 8, 40
    half_width = len(stages) * tile + (len(stages) - 1) * gap
    sheet = Image.new("RGB", (2 * half_width + middle, len(blocks) * tile + (len(blocks) - 1) * gap),
                      (255, 255, 255))
    for row, block in enumerate(blocks):
        y = row * (tile + gap)
        for col, stage in enumerate(stages):
            for side, java in ((0, True), (half_width + middle, False)):
                face = big(blend(block, vanilla[stage], java), tile // 16)
                sheet.paste(face.convert("RGB"), (side + col * (tile + gap), y))
    sheet.save(ROOT / "images/comparison.png", optimize=True)
    print("Wrote", OUT, "pack.png, icon.png and images/comparison.png")


if __name__ == "__main__":
    main()
