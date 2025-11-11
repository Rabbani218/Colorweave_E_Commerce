from app import app, db
from app.models import Product, Event

def test_personalized_recommendations(tmp_path):
    with app.app_context():
        db.create_all()
        if not Product.query.get(301):
            p1 = Product(id=301, name='Delta', price=11)
            p2 = Product(id=302, name='Epsilon', price=22)
            p3 = Product(id=303, name='Zeta', price=33)
            db.session.add_all([p1,p2,p3])
            db.session.commit()
        # simulate session events
        evs = [
            Event(session_id='sessP', product_id=301, event_type='view'),
            Event(session_id='sessP', product_id=302, event_type='view'),
            Event(session_id='sessP', product_id=302, event_type='add_to_cart')
        ]
        db.session.add_all(evs)
        db.session.commit()
    client = app.test_client()
    with client.session_transaction() as s:
        s['sid'] = 'sessP'
    r = client.get('/api/ai/recommend_for_user')
    assert r.status_code == 200
    data = r.get_json()
    assert 'items' in data
