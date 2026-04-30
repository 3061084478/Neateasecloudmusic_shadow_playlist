from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont


def _remove_near_white_background(image: Image.Image) -> Image.Image:
    src = image.convert("RGBA")
    pixels = src.load()
    width, height = src.size
    for y in range(height):
        for x in range(width):
            r, g, b, a = pixels[x, y]
            max_delta = max(abs(r - g), abs(g - b), abs(r - b))
            if r >= 226 and g >= 226 and b >= 226 and max_delta <= 24:
                a = 0
            elif r >= 210 and g >= 210 and b >= 210 and max_delta <= 18:
                a = max(0, a - 110)
            pixels[x, y] = (r, g, b, a)
    return src


def _load_brand_font(size: int) -> ImageFont.ImageFont:
    candidates = [
        r"C:\Windows\Fonts\BRUSHSCI.TTF",
        r"C:\Windows\Fonts\SEGOESCR.TTF",
        r"C:\Windows\Fonts\Inkfree.ttf",
        r"C:\Windows\Fonts\segscript.ttf",
        r"C:\Windows\Fonts\comic.ttf",
        r"C:\Windows\Fonts\comicbd.ttf",
        r"C:\Windows\Fonts\timesbi.ttf",
    ]
    for path in candidates:
        if Path(path).exists():
            return ImageFont.truetype(path, size=size)
    return ImageFont.load_default()


def _draw_shadow_wordmark(
    canvas: Image.Image,
    x: int,
    y: int,
) -> tuple[tuple[int, int, int, int], tuple[int, int, int, int]]:
    draw = ImageDraw.Draw(canvas)
    font = _load_brand_font(132)
    text = "Shadow"
    prefix = "Shad"
    target = "o"
    text_bbox = draw.textbbox((x, y), text, font=font, stroke_width=2)

    prefix_width = int(draw.textlength(prefix, font=font))
    target_width = int(draw.textlength(target, font=font))
    o_x = x + prefix_width
    o_bbox = draw.textbbox((o_x, y), target, font=font, stroke_width=2)

    # thicker underpaint for stronger graffiti weight
    draw.text((x - 2, y + 2), text, font=font, fill=(20, 20, 20, 118))
    draw.text((x + 2, y + 1), text, font=font, fill=(14, 14, 14, 96))
    draw.text((x + 1, y - 1), text, font=font, fill=(255, 255, 255, 56))
    draw.text((x, y + 1), text, font=font, fill=(6, 6, 6, 162))
    draw.text((x - 1, y), text, font=font, fill=(8, 8, 8, 112))
    # main wordmark (boldened by larger stroke)
    draw.text(
        (x, y),
        text,
        font=font,
        fill=(5, 5, 5, 248),
        stroke_width=4,
        stroke_fill=(255, 255, 255, 178),
    )
    return (
        (int(text_bbox[0]), int(text_bbox[1]), int(text_bbox[2]), int(text_bbox[3])),
        (int(o_bbox[0]), int(o_bbox[1]), int(o_bbox[2]), int(o_bbox[3])),
    )


def _add_logo_glow(canvas: Image.Image, logo_layer: Image.Image) -> None:
    alpha_mask = logo_layer.split()[3]
    if alpha_mask.getbbox() is None:
        return

    outer = Image.new("RGBA", logo_layer.size, (236, 245, 255, 0))
    outer.putalpha(alpha_mask)
    outer = outer.filter(ImageFilter.GaussianBlur(radius=18))
    outer = Image.blend(Image.new("RGBA", outer.size, (0, 0, 0, 0)), outer, alpha=0.62)
    canvas.alpha_composite(outer, (0, 0))

    inner = Image.new("RGBA", logo_layer.size, (210, 226, 255, 0))
    inner.putalpha(alpha_mask)
    inner = inner.filter(ImageFilter.GaussianBlur(radius=8))
    inner = Image.blend(Image.new("RGBA", inner.size, (0, 0, 0, 0)), inner, alpha=0.58)
    canvas.alpha_composite(inner, (0, 0))


def _soften_butterfly_tone(image: Image.Image) -> Image.Image:
    src = image.convert("RGBA")
    pixels = src.load()
    width, height = src.size
    for y in range(height):
        for x in range(width):
            r, g, b, a = pixels[x, y]
            if a == 0:
                continue
            gray = int((r + g + b) / 3)
            # lift dark details to light gray and reduce chroma for cleaner white/gray wings
            if gray < 150:
                gray = int(gray * 0.45 + 150 * 0.55)
            gray = int(gray * 0.92 + 8)
            r2 = int(gray * 0.97)
            g2 = int(gray * 0.98)
            b2 = int(gray * 1.00)
            # Make butterfly body/wings solid to ensure clear cover over text.
            a2 = 255 if a >= 36 else 0
            pixels[x, y] = (r2, g2, b2, a2)
    return src


def render_brand_draft(source_path: Path, output_dir: Path) -> tuple[Path, Path]:
    if not source_path.exists():
        raise RuntimeError(f"无法读取图片: {source_path}")
    original = Image.open(source_path)

    butterfly = _remove_near_white_background(original)
    butterfly = _soften_butterfly_tone(butterfly)
    bbox = butterfly.getbbox()
    if bbox:
        butterfly = butterfly.crop(bbox)
    butterfly.thumbnail((120, 96), Image.Resampling.LANCZOS)

    canvas = Image.new("RGBA", (1220, 320), (0, 0, 0, 0))
    logo_layer = Image.new("RGBA", canvas.size, (0, 0, 0, 0))

    text_bbox, o_bbox = _draw_shadow_wordmark(logo_layer, 268, 88)
    # place butterfly above the "o" and overlap upper half of the letter.
    o_center_x = (o_bbox[0] + o_bbox[2]) // 2
    o_top_y = o_bbox[1]
    butterfly_x = int(o_center_x - butterfly.width * 0.54) + 48
    butterfly_y = int(o_top_y - butterfly.height * 0.78)-2
    logo_layer.alpha_composite(butterfly, (butterfly_x, butterfly_y))

    # render a unified halo around the entire logo group (butterfly + wordmark).
    _add_logo_glow(canvas, logo_layer)
    canvas.alpha_composite(logo_layer, (0, 0))

    output_dir.mkdir(parents=True, exist_ok=True)
    transparent_path = output_dir / "shadow_brand_draft_A.png"
    canvas.save(transparent_path, format="PNG")

    preview = Image.new("RGBA", canvas.size, (17, 22, 31, 255))
    preview.alpha_composite(canvas, (0, 0))
    preview_path = output_dir / "shadow_brand_draft_A_preview_dark.png"
    preview.save(preview_path, format="PNG")

    return transparent_path, preview_path


if __name__ == "__main__":
    src = Path(
        r"C:\Users\ASUS\xwechat_files\wxid_yb29vugsgq4x12_8d60\temp\RWTemp\2026-04\9e20f478899dc29eb19741386f9343c8\ce3fa50dacb6a6e9397afb87ceb45cdd.jpg"
    )
    out = Path(r"C:\Users\ASUS\Desktop\网易云\V5\assets\brand_drafts")
    transparent, preview_dark = render_brand_draft(src, out)
    print(transparent)
    print(preview_dark)
