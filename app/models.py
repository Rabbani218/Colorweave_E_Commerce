from .extensions import db
from werkzeug.security import generate_password_hash, check_password_hash  # type: ignore
from flask_login import UserMixin  # type: ignore
from datetime import datetime, timezone


class Product(db.Model):
    __tablename__ = 'product'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    price = db.Column(db.Integer, default=0)
    description = db.Column(db.Text, default='')
    image = db.Column(db.String(256), default='')
    stock = db.Column(db.Integer, default=0)

    def __repr__(self):
        return f"<Product {self.id} {self.name}>"


class User(UserMixin, db.Model):
    __tablename__ = 'user'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    is_admin = db.Column(db.Boolean, default=False)
    # Extended profile fields (added dynamically if missing):
    email = db.Column(db.String(120), unique=True, nullable=True)
    bio = db.Column(db.Text, nullable=True)
    avatar = db.Column(db.String(256), nullable=True)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    # UserMixin provides is_authenticated, is_active, get_id, etc.


class Event(db.Model):
    __tablename__ = 'event'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    session_id = db.Column(db.String(64), index=True)
    product_id = db.Column(db.Integer, db.ForeignKey('product.id'), nullable=True)
    event_type = db.Column(db.String(32), nullable=False)  # view, add_to_cart, search, chat
    # Use timezone-aware UTC universally (compatible with Python <3.11 where datetime.UTC is absent)
    _utcnow = lambda: datetime.now(timezone.utc)
    created_at = db.Column(db.DateTime(timezone=True), default=_utcnow, index=True)

    def __repr__(self):
        return f"<Event {self.event_type} u={self.user_id} s={self.session_id} p={self.product_id}>"
