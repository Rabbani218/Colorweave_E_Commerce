from app import app, db
from app.models import Product, Event

def test_cf_and_hybrid_endpoints(tmp_path):
    with app.app_context():
        db.create_all()
        # seed products
        if not Product.query.get(101):
            p1 = Product(id=101, name='Alpha', price=10)
            p2 = Product(id=102, name='Beta', price=20)
            p3 = Product(id=103, name='Gamma', price=30)
            db.session.add_all([p1,p2,p3])
            db.session.commit()
        # create co-occurrence events (Alpha & Beta together)
        ev = Event(session_id='sessX', product_id=101, event_type='view')
        ev2 = Event(session_id='sessX', product_id=102, event_type='view')
        db.session.add_all([ev, ev2])
        db.session.commit()

    client = app.test_client()
    r1 = client.get('/api/ai/recommend_cf?product_id=101')
    assert r1.status_code == 200
    data = r1.get_json()
    assert 'items' in data
    r2 = client.get('/api/ai/recommend_hybrid?product_id=101')
    assert r2.status_code == 200
    data2 = r2.get_json()
    assert 'items' in data2
