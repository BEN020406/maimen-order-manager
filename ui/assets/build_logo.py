#!/usr/bin/env python3
"""一次性资源构建脚本：把原始 logo 图片处理成可用的透明 PNG 与 favicon。

需要 Pillow（仅本脚本使用；技能运行时是纯标准库）。

用法：
  python build_logo.py <源图片> [输出目录]

处理流程：
1. 从四角泛洪填充，只去掉**外部连通**的白底，保留票券内部的奶油色；
2. 按 alpha 边界裁掉多余留白，补成正方形；
3. 缩放出 512 / 192 / 64 与 favicon.ico。
"""

from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

MAGIC = (255, 0, 254)  # 泛洪填充用的魔法色，logo 中不存在
PADDING_RATIO = 0.06


def remove_background(source: Path) -> Image.Image:
    rgb = Image.open(source).convert("RGB")
    width, height = rgb.size
    # 只填外部白底：泛洪填充不会进入被轮廓包住的内部奶油色区域
    for seed in ((0, 0), (width - 1, 0), (0, height - 1), (width - 1, height - 1)):
        ImageDraw.floodfill(rgb, seed, MAGIC, thresh=24)

    alpha = Image.new("L", rgb.size, 255)
    pixels = rgb.load()
    alpha_pixels = alpha.load()
    for y in range(height):
        for x in range(width):
            if pixels[x, y] == MAGIC:
                alpha_pixels[x, y] = 0

    # 腐蚀 1px 去掉 JPEG 边缘白边，再轻微模糊让边缘自然
    alpha = alpha.filter(ImageFilter.MinFilter(3))
    alpha = alpha.filter(ImageFilter.GaussianBlur(0.6))

    rgba = rgb.convert("RGBA")
    rgba.putalpha(alpha)
    return rgba


def square_crop(image: Image.Image) -> Image.Image:
    bbox = image.getbbox()
    if not bbox:
        raise SystemExit("没有检测到有效内容")
    trimmed = image.crop(bbox)
    side = max(trimmed.size)
    pad = int(side * PADDING_RATIO)
    canvas = Image.new("RGBA", (side + pad * 2, side + pad * 2), (0, 0, 0, 0))
    canvas.paste(
        trimmed,
        ((canvas.width - trimmed.width) // 2, (canvas.height - trimmed.height) // 2),
        trimmed,
    )
    return canvas


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    source = Path(sys.argv[1])
    out_dir = Path(sys.argv[2]) if len(sys.argv) > 2 else source.parent
    out_dir.mkdir(parents=True, exist_ok=True)

    logo = square_crop(remove_background(source))
    print(f"源图 {source.name} → 方形画布 {logo.size}")

    for size in (512, 192, 64):
        resized = logo.resize((size, size), Image.LANCZOS)
        target = out_dir / f"logo-{size}.png"
        resized.save(target, "PNG", optimize=True)
        print(f"写出 {target}")

    logo.resize((512, 512), Image.LANCZOS).save(
        out_dir / "favicon.ico",
        sizes=[(16, 16), (32, 32), (48, 48), (64, 64)],
    )
    print(f"写出 {out_dir / 'favicon.ico'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
