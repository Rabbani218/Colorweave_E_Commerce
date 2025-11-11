from app import app, db
from app.models import Product, Event, User

def test_admin_analytics_page(tmp_path):
    with app.app_context():
        db.create_all()
        # Ensure admin exists
        if not User.query.filter_by(username='admin').first():
            u = User(username='admin')
            u.set_password('adminpass')
            u.is_admin = True
            db.session.add(u)
            db.session.commit()
        # seed product and events
        if not Product.query.get(201):
            p = Product(id=201, name='Analytic Product', price=50)
            db.session.add(p)
            db.session.commit()
        e = Event(session_id='sessY', product_id=201, event_type='view')
        db.session.add(e)
        db.session.commit()

    client = app.test_client()
    client.post('/admin/login', data={'username': 'admin', 'password': 'adminpass'})
    resp = client.get('/admin/analytics')
    assert resp.status_code == 200
    assert b'Analytics Dashboard' in resp.data
