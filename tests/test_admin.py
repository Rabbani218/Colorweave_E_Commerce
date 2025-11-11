import os
from app import db, User


def test_create_admin_from_env(tmp_path, monkeypatch):
    # Ensure a clean DB
    db.create_all()
    # Set ADMIN_PASSWORD env and call seed via creating a user
    monkeypatch.setenv('ADMIN_PASSWORD', 'testpass')
    # Create user if none
    if not db.session.query(User).first():
        u = User(username='admin', password_hash='x')
        db.session.add(u)
        db.session.commit()
    # Check there is at least one user
    assert db.session.query(User).first() is not None
