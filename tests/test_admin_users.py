import os
import pytest


class TestConfig:
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    SECRET_KEY = 'test-secret'


@pytest.fixture
def app():
    # Ensure admin seed happens
    os.environ['ADMIN_PASSWORD'] = 'adminpass'
    from app import create_app
    from app.extensions import db

    app = create_app(config_object=TestConfig)

    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()


@pytest.fixture
def client(app):
    return app.test_client()


def test_admin_seed_and_login(client):
    from app.extensions import db
    from app.models import User

    # Admin should have been created from ADMIN_PASSWORD
    admin = User.query.filter_by(username='admin').first()
    assert admin is not None and admin.is_admin

    # Login via form
    rv = client.post('/admin/login', data={'username': 'admin', 'password': 'adminpass'}, follow_redirects=True)
    assert b'Logged in as admin' in rv.data or b'Logged in' in rv.data


def test_create_edit_delete_user(client):
    from app.models import User

    # login as admin
    client.post('/admin/login', data={'username': 'admin', 'password': 'adminpass'})

    # create user
    rv = client.post('/admin/users/create', data={'username': 'alice', 'password': 'pw', 'is_admin': 'on'}, follow_redirects=True)
    assert b'User created' in rv.data
    u = User.query.filter_by(username='alice').first()
    assert u is not None and u.is_admin

    # edit user
    rv = client.post(f'/admin/users/edit/{u.id}', data={'username': 'alice2', 'password': 'newpw'}, follow_redirects=True)
    assert b'User updated' in rv.data
    u = User.query.get(u.id)
    assert u.username == 'alice2'

    # delete user
    rv = client.get(f'/admin/users/delete/{u.id}', follow_redirects=True)
    assert b'User deleted' in rv.data
    assert User.query.filter_by(username='alice2').first() is None
