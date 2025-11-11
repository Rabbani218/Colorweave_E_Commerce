from app import app, db, Product


def test_cart_total_in_session(tmp_path):
    # Ensure DB exists and has products
    db.create_all()
    # Add one product if missing
    if not Product.query.get(1):
        p = Product(id=1, name='ColorWeave Bracelet', price=5000, stock=10, image='Bracelet1.jpg')
        db.session.add(p)
        db.session.commit()

    client = app.test_client()
    with client.session_transaction() as sess:
        sess['cart'] = [{'id':1,'name':'ColorWeave Bracelet','price':5000,'quantity':2}]
    resp = client.get('/cart')
    assert resp.status_code == 200
    data = resp.get_data(as_text=True)
    # Total should be 10000 (5000 * 2)
    assert '10000' in data
