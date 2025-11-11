from flask import Blueprint, render_template, request, redirect, url_for, flash, session, abort  # type: ignore
from flask_login import login_user, logout_user, login_required, current_user  # type: ignore
from .utils import load_products, get_product_by_id, seed_db_from_json, log_event
from .extensions import db
from .models import User
from .models import Product
from werkzeug.utils import secure_filename  # type: ignore
import os
from datetime import datetime
import os

ALLOW_DEV_ADMIN = os.environ.get('ALLOW_DEV_ADMIN', '0') in {'1', 'true', 'True'}

main_bp = Blueprint('main', __name__)


def ensure_seed():
    try:
        seed_db_from_json()
    except Exception:
        pass


@main_bp.route('/')
def home():
    return render_template('home.html')


@main_bp.route('/about')
def about():
    return render_template('about.html')


@main_bp.route('/products')
def products():
    try:
        products_data = load_products()
        return render_template('products.html', products=products_data)
    except Exception as e:
        flash('Error loading products', 'error')
        return redirect(url_for('main.home'))


@main_bp.route('/product/<int:product_id>')
def product_detail(product_id):
    product = get_product_by_id(product_id)
    if not product:
        flash('Produk tidak ditemukan.', 'error')
        return redirect(url_for('main.products'))
    try:
        log_event('view', product_id)
    except Exception:
        pass
    return render_template('product_detail.html', product=product)


@main_bp.route('/contact')
def contact():
    return render_template('contact.html')


@main_bp.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('main.home'))
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        if not username or not password:
            flash('Username and password required.', 'error')
            return redirect(url_for('main.register'))
        if User.query.filter_by(username=username).first():
            flash('Username already exists.', 'error')
            return redirect(url_for('main.register'))
        u = User(username=username)
        u.set_password(password)
        db.session.add(u)
        db.session.commit()
        login_user(u)
        flash('Registration successful. You are now logged in.', 'success')
        return redirect(url_for('main.home'))
    return render_template('register.html')


@main_bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('main.home'))
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        user = User.query.filter_by(username=username).first()
        if user and user.check_password(password):
            login_user(user)
            flash('Logged in.', 'success')
            return redirect(url_for('main.home'))
        flash('Invalid username or password.', 'error')
    return render_template('login.html')


@main_bp.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Logged out.', 'success')
    return redirect(url_for('main.home'))


@main_bp.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    user: User = current_user  # type: ignore
    if request.method == 'POST':
        user.username = request.form.get('username') or user.username
        email = request.form.get('email')
        bio = request.form.get('bio')
        if email is not None:
            user.email = email
        if bio is not None:
            user.bio = bio
        # handle avatar upload
        file = request.files.get('avatar')
        if file and file.filename:
            fname = secure_filename(file.filename)
            # only allow images
            if os.path.splitext(fname)[1].lower() in {'.png', '.jpg', '.jpeg', '.gif', '.webp'}:
                ts = datetime.utcnow().strftime('%Y%m%d%H%M%S')
                ext = os.path.splitext(fname)[1].lower()
                new_name = f"u{user.id}_{ts}{ext}"
                base = current_user._get_current_object()  # type: ignore
                # save into static/images/avatars
                from flask import current_app
                folder = os.path.join(current_app.static_folder or 'static', 'images', 'avatars')
                os.makedirs(folder, exist_ok=True)
                path = os.path.join(folder, new_name)
                file.save(path)
                user.avatar = new_name
        try:
            db.session.commit()
            flash('Profile updated.', 'success')
        except Exception:
            db.session.rollback()
            flash('Could not update profile.', 'error')
        return redirect(url_for('main.profile'))
    return render_template('profile.html', user=user)


@main_bp.route('/dev/make_admin')
@login_required
def dev_make_admin():
    """Promote current user to admin if dev flag enabled. Helpful to access /admin quickly.
    Guarded by ALLOW_DEV_ADMIN env to avoid accidental elevation in production.
    """
    if not ALLOW_DEV_ADMIN:
        flash('Dev admin elevation disabled.', 'error')
        return redirect(url_for('main.profile'))
    user: User = current_user  # type: ignore
    if user.is_admin:
        flash('Already an admin.', 'success')
        return redirect(url_for('admin.index'))
    try:
        user.is_admin = True
        db.session.commit()
        flash('You are now an admin.', 'success')
        return redirect(url_for('admin.index'))
    except Exception:
        db.session.rollback()
        flash('Could not elevate to admin.', 'error')
        return redirect(url_for('main.profile'))


# --- Cart endpoints (session-backed) -------------------------------------------------
@main_bp.route('/add_to_cart', methods=['POST'])
def add_to_cart():
    # Accept either 'product_id' or 'id' in the form for compatibility
    pid = request.form.get('product_id') or request.form.get('id') or request.form.get('product')
    try:
        pid = int(pid)
    except Exception:
        flash('Invalid product.', 'error')
        return redirect(url_for('main.products'))
    prod = Product.query.get(pid)
    if not prod:
        flash('Product not found.', 'error')
        return redirect(url_for('main.products'))

    cart = session.get('cart', [])
    # find existing item
    for it in cart:
        if int(it.get('id')) == prod.id:
            it['quantity'] = int(it.get('quantity', 0)) + 1
            break
    else:
        cart.append({'id': prod.id, 'name': prod.name, 'price': prod.price, 'quantity': 1, 'image': prod.image})
    session['cart'] = cart
    try:
        log_event('add_to_cart', prod.id)
    except Exception:
        pass
    flash('Added to cart.', 'success')
    return redirect(request.referrer or url_for('main.products'))


@main_bp.route('/cart')
def cart():
    cart = session.get('cart', [])
    cart_items = []
    total = 0
    for it in cart:
        qty = int(it.get('quantity', 0))
        price = int(it.get('price', 0))
        total += qty * price
        cart_items.append(it)
    return render_template('Cart.html', cart_items=cart_items, cart_total=total)


@main_bp.route('/update_cart/<int:item_id>', methods=['POST'])
def update_cart(item_id):
    qty = request.form.get('quantity')
    try:
        qty = int(qty)
    except Exception:
        qty = None
    cart = session.get('cart', [])
    new_cart = []
    for it in cart:
        if int(it.get('id')) == item_id:
            if qty and qty > 0:
                it['quantity'] = qty
                new_cart.append(it)
            # else remove
        else:
            new_cart.append(it)
    session['cart'] = new_cart
    flash('Cart updated.', 'success')
    return redirect(url_for('main.cart'))


@main_bp.route('/remove_from_cart/<int:item_id>')
def remove_from_cart(item_id):
    cart = session.get('cart', [])
    cart = [it for it in cart if int(it.get('id')) != item_id]
    session['cart'] = cart
    flash('Item removed from cart.', 'success')
    return redirect(url_for('main.cart'))
