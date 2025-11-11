import io
from app import app, db
from app.models import Product, User


def test_ai_search_and_recommend(tmp_path):
    # Ensure DB
    db.create_all()
    # seed products
    if not Product.query.get(1):
        p1 = Product(id=1, name='Blue Bracelet', price=100, description='Handmade blue bracelet', image='bracelet1.svg')
        p2 = Product(id=2, name='Red Necklace', price=200, description='Stylish red necklace', image='necklace1.svg')
        db.session.add_all([p1, p2])
        db.session.commit()

    client = app.test_client()
    # semantic search
    resp = client.get('/api/ai/search?q=blue')
    assert resp.status_code == 200
    data = resp.get_json()
    assert 'items' in data

    # recommend for product
    resp = client.get('/api/ai/recommend?product_id=1')
    assert resp.status_code == 200
    data = resp.get_json()
    assert 'items' in data


def test_ai_generate_image_admin(tmp_path):
    db.create_all()
    # Create admin user and login
    if not User.query.filter_by(username='admin').first():
        u = User(username='admin')
        u.set_password('adminpw')
        u.is_admin = True
        db.session.add(u)
        db.session.commit()

    client = app.test_client()
    # login
    client.post('/admin/login', data={'username': 'admin', 'password': 'adminpw'})
    resp = client.post('/api/ai/generate_image', data={'prompt': 'A test product image'})
    assert resp.status_code in (200, 302)
    # If 200, check path
    if resp.status_code == 200:
        data = resp.get_json()
        assert 'path' in data
