import pytest  # type: ignore
from app import create_app
from app.utils import load_products, get_product_by_id  # type: ignore

app = create_app()


def test_load_products():
    with app.app_context():
        products = load_products()
        assert isinstance(products, list)
        assert len(products) >= 1


def test_get_product_by_id():
    with app.app_context():
        p = get_product_by_id(1)
        assert p is not None
        assert int(p.get('id')) == 1
