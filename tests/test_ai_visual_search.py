import io
from app import app, db
from app.models import Product
from PIL import Image  # type: ignore
import os


def test_visual_search_with_uploaded_image(tmp_path):
    with app.app_context():
        db.create_all()
        # Ensure at least one product with a real image on disk
        static_images = os.path.join(app.static_folder, 'images')
        os.makedirs(static_images, exist_ok=True)
        img_path = os.path.join(static_images, 'vs_test_blue.png')
        if not os.path.isfile(img_path):
            im = Image.new('RGB', (64, 64), color=(0, 0, 200))
            im.save(img_path)
        if not Product.query.filter_by(name='VS Test Blue').first():
            p = Product(name='VS Test Blue', price=123, image='vs_test_blue.png', stock=5)
            db.session.add(p)
            db.session.commit()

    client = app.test_client()
    # Upload a blue-ish query image
    bio = io.BytesIO()
    qimg = Image.new('RGB', (64,64), color=(0,0,180))
    qimg.save(bio, format='PNG')
    bio.seek(0)
    data = {'image': (bio, 'query.png')}
    resp = client.post('/api/ai/visual_search', data=data, content_type='multipart/form-data')
    assert resp.status_code == 200
    data = resp.get_json()
    assert 'items' in data
    assert isinstance(data['items'], list)
