import os
import json
from typing import List, Tuple
from PIL import Image  # type: ignore

from ..models import Product


def _hist_feature(img: Image.Image) -> List[float]:
    """Compute a simple normalized RGB histogram feature (768 dims)."""
    img = img.convert('RGB')
    hist = img.histogram()  # 256*3 bins
    # Normalize L2
    s = sum(float(x) * float(x) for x in hist) or 1.0
    import math
    norm = math.sqrt(s)
    return [float(x) / norm for x in hist]


def _l2(a: List[float], b: List[float]) -> float:
    return sum((x - y) * (x - y) for x, y in zip(a, b)) ** 0.5


class VisionIndexer:
    """Very lightweight visual search using RGB histograms.

    This avoids heavy dependencies and works entirely with Pillow.
    """

    def __init__(self, static_folder: str, persist_dir: str | None = None):
        self.static_folder = static_folder
        self.persist_dir = persist_dir
        self.ids: List[int] = []
        self.features: List[List[float]] = []

    def _product_image_path(self, image_name: str) -> str:
        return os.path.join(
            self.static_folder or 'static',
            'images',
            image_name)

    def build_index(self, force: bool = False):
        # Try load cache first
        cache_path = None
        if self.persist_dir:
            os.makedirs(self.persist_dir, exist_ok=True)
            cache_path = os.path.join(self.persist_dir, 'vision_features.json')
            if not force and os.path.isfile(cache_path):
                try:
                    with open(cache_path, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                    self.ids = data.get('ids', [])
                    self.features = data.get('features', [])
                    if self.ids and self.features:
                        return
                except Exception:
                    pass

        # Build fresh
        ids: List[int] = []
        feats: List[List[float]] = []
        for p in Product.query.order_by(Product.id).all():
            if not p.image:
                continue
            path = self._product_image_path(p.image)
            if not os.path.isfile(path):
                continue
            try:
                with Image.open(path) as im:
                    f = _hist_feature(im)
                ids.append(p.id)
                feats.append(f)
            except Exception:
                continue
        self.ids = ids
        self.features = feats

        # Save cache
        if cache_path:
            try:
                with open(cache_path, 'w', encoding='utf-8') as f:
                    json.dump({'ids': ids, 'features': feats}, f)
            except Exception:
                pass

    def query_image(self, img: Image.Image,
                    k: int = 8) -> List[Tuple[int, float]]:
        if not self.ids:
            self.build_index()
        if not self.ids:
            return []
        q = _hist_feature(img)
        scored = [(pid, _l2(q, f)) for pid, f in zip(self.ids, self.features)]
        scored.sort(key=lambda x: x[1])
        return scored[:k]
