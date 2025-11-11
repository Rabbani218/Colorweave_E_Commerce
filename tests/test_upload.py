import io
from app import create_app
from app.extensions import db
from app.models import Product, User
app = create_app()
from werkzeug.security import generate_password_hash  # type: ignore


def test_image_upload(tmp_path):
    # ensure DB schema exists
    with app.app_context():
        db.create_all()

    client = app.test_client()

    # create a simple PNG in memory
    img_bytes = io.BytesIO()
    from PIL import Image  # type: ignore

    im = Image.new('RGB', (100, 100), color=(73, 109, 137))
    im.save(img_bytes, format='PNG')
    img_bytes.seek(0)

    data = {
        'name': 'UploadTest',
        'price': '123',
        'stock': '5',
        'image_file': (img_bytes, 'test.png')
    }
    resp = client.post('/admin/add', data=data, content_type='multipart/form-data', follow_redirects=True)
    assert resp.status_code == 200
    assert b'Product added' in resp.data
