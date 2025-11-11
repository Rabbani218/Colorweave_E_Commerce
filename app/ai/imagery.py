import os
from PIL import Image, ImageDraw, ImageFont  # type: ignore


def generate_image(prompt: str, filename: str, out_dir: str):
    """Generate a placeholder image containing the prompt text.

    This is a lightweight local fallback so the project can function without
    external image APIs. Saved file path is returned.
    """
    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, filename)
    # Create simple image
    img = Image.new('RGB', (512, 512), color=(255, 255, 255))
    d = ImageDraw.Draw(img)
    try:
        fnt = ImageFont.load_default()
    except Exception:
        fnt = None
    text = (prompt or 'Generated')[:200]
    d.text((10, 10), text, fill=(0, 0, 0), font=fnt)
    img.save(path, 'PNG')
    return path
