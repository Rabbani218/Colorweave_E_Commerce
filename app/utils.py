import os
import json
from io import BytesIO
from PIL import Image
from .extensions import db
from .models import Product, Event
from flask import session
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
IMAGES_DIR = os.path.join(BASE_DIR, 'static', 'images')

def _webp_name(fname: str) -> str:
    """Return expected webp filename for source image."""
    base, ext = os.path.splitext(fname)
    return base + '.webp'

def ensure_webp_thumbnail(image_name: str, max_width: int = 600) -> str | None:
    """Create a WebP thumbnail for an existing image if not present.

    Returns path to created webp (filename only) or existing one. Returns None if source missing.
    Non-fatal: silently skips errors (to avoid breaking request path).
    """
    try:
        if not image_name:
            return None
        src_path = os.path.join(IMAGES_DIR, image_name)
        if not os.path.isfile(src_path):
            return None
        webp_file = _webp_name(image_name)
        webp_path = os.path.join(IMAGES_DIR, webp_file)
        if os.path.isfile(webp_path):
            return webp_file
        with Image.open(src_path) as im:
            im = im.convert('RGBA') if im.mode in ('P','LA') else im.convert('RGB')
            w, h = im.size
            if w > max_width:
                new_h = int(h * (max_width / w))
                im = im.resize((max_width, new_h), Image.LANCZOS)
            # Save webp optimized
            im.save(webp_path, 'WEBP', quality=82, method=6)
        return webp_file
    except Exception:
        return None


def load_products():
    """Return list of products from DB; if empty, attempt to seed from data/products.json."""
    try:
        db.create_all()
    except Exception:
        pass
    prods = []
    for p in Product.query.order_by(Product.id).all():
        prods.append({
            'id': p.id,
            'name': p.name,
            'price': p.price,
            'description': p.description,
            'image': p.image,
            'stock': p.stock,
        })
    return prods


def get_product_by_id(product_id):
    try:
        p = Product.query.get(int(product_id))
        if not p:
            return None
        return {'id': p.id, 'name': p.name, 'price': p.price, 'description': p.description, 'image': p.image, 'stock': p.stock}
    except Exception:
        return None


def seed_db_from_json():
    data_path = os.path.join(BASE_DIR, 'data', 'products.json')
    if not os.path.isfile(data_path):
        return
    with open(data_path, 'r', encoding='utf-8') as f:
        items = json.load(f)
    for it in items:
        prod = Product(
            id=int(it.get('id')) if it.get('id') else None,
            name=it.get('name'),
            price=int(it.get('price', 0)),
            description=it.get('description', ''),
            image=it.get('image', ''),
            stock=int(it.get('stock', 0)),
        )
        db.session.merge(prod)
    db.session.commit()
    # Attempt to generate webp thumbnails for seeded images (best effort)
    try:
        for it in items:
            img = it.get('image')
            ensure_webp_thumbnail(img)
    except Exception:
        pass


def _ensure_session_id():
    sid = session.get('sid')
    if not sid:
        import secrets
        sid = secrets.token_hex(16)
        session['sid'] = sid
    return sid


def log_event(event_type: str, product_id: int | None = None):
    try:
        sid = _ensure_session_id()
        ev = Event(session_id=sid, product_id=product_id, event_type=event_type, created_at=datetime.utcnow())
        db.session.add(ev)
        db.session.commit()
    except Exception:
        try:
            db.session.rollback()
        except Exception:
            pass
