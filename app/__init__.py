import os
from flask import Flask
from flask_cors import CORS  # type: ignore

# Load .env if python-dotenv is available (optional)
try:
    from dotenv import load_dotenv  # type: ignore
    load_dotenv()
except Exception:
    pass
import config as _config  # project-level config module


def create_app(config_object=None):
    """Application factory for ColorWeave."""
    # Templates/static live at repository root 'templates' and 'static'
    top = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    template_folder = os.path.join(top, 'templates')
    static_folder = os.path.join(top, 'static')
    app = Flask(__name__, instance_relative_config=False, template_folder=template_folder, static_folder=static_folder)
    # Enable CORS for API endpoints (configurable origins)
    CORS(app, resources={r"/api/*": {"origins": os.environ.get('CORS_ORIGINS', '*')}})
    # Security headers & cookie flags
    app.config.setdefault('SESSION_COOKIE_HTTPONLY', True)
    app.config.setdefault('SESSION_COOKIE_SAMESITE', 'Lax')
    # Allow opting into secure cookies via env
    if os.environ.get('FORCE_SECURE_COOKIES'):
        app.config['SESSION_COOKIE_SECURE'] = True

    @app.after_request
    def _secure_headers(resp):
        resp.headers.setdefault('X-Content-Type-Options', 'nosniff')
        resp.headers.setdefault('X-Frame-Options', 'DENY')
        resp.headers.setdefault('Referrer-Policy', 'strict-origin-when-cross-origin')
        # Minimal CSP allowing Bootstrap CDN & inline styles for now
        csp = (
            "default-src 'self'; script-src 'self' https://cdn.jsdelivr.net; style-src 'self' https://cdn.jsdelivr.net 'unsafe-inline'; "
            "img-src 'self' data: blob:; connect-src 'self';"
        )
        resp.headers.setdefault('Content-Security-Policy', csp)
        resp.headers.setdefault('Permissions-Policy', 'geolocation=(), microphone=(), camera=()')
        return resp

    @app.route('/health')
    def health():
        return {'status': 'ok'}, 200

    # Basic config: prefer provided object, otherwise load from env or config.py
    if config_object:
        app.config.from_object(config_object)
    else:
        # Use FLASK_CONFIG env to choose a config class from config.py
        cfg_name = os.environ.get('FLASK_CONFIG', '').lower()
        if cfg_name == 'production':
            app.config.from_object(_config.ProductionConfig)
        elif cfg_name == 'development':
            app.config.from_object(_config.DevelopmentConfig)
        else:
            app.config.from_object(_config.Config)

    # Initialize extensions
    from .extensions import db, migrate, login_manager, flask_session
    # Ensure a session backend is configured (filesystem fallback)
    app.config.setdefault('SESSION_TYPE', app.config.get('SESSION_TYPE') or 'filesystem')

    # Ensure data directories exist for SQLite file and instance path
    try:
        os.makedirs(os.path.join(app.root_path, 'data'), exist_ok=True)
    except Exception:
        pass
    try:
        os.makedirs(os.path.join(app.instance_path, 'data'), exist_ok=True)
    except Exception:
        pass
    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)
    flask_session.init_app(app)

    # Template filters
    def _format_idr(value):
        try:
            n = int(value)
            return ("Rp " + format(n, ",").replace(",", "."))
        except Exception:
            return f"Rp {value}"
    try:
        app.jinja_env.filters['idr'] = _format_idr
    except Exception:
        pass

    # Configure login loader (deferred import to avoid circulars)
    from .models import User  # type: ignore

    @login_manager.user_loader
    def _load_user(user_id):
        try:
            return User.query.get(int(user_id))
        except Exception:
            return None

    # Register blueprints / routes
    from .routes import main_bp  # type: ignore
    app.register_blueprint(main_bp)

    from .admin import admin_bp  # type: ignore
    app.register_blueprint(admin_bp, url_prefix='/admin')

    # Register AI blueprint if present
    try:
        from .ai.routes import ai_bp  # type: ignore
        app.register_blueprint(ai_bp, url_prefix='/api/ai')
    except Exception:
        pass

    # --- Create compatibility top-level endpoint aliases for legacy templates/tests ---
    try:
        # import view callables from routes so we can register them as top-level endpoints
        from . import routes as _routes  # type: ignore
        # map common endpoints without blueprint prefix (templates sometimes use these)
        aliases = [
            ('/product/<int:product_id>', 'product_detail', _routes.product_detail, ['GET']),
            ('/products', 'products', _routes.products, ['GET']),
            ('/add_to_cart', 'add_to_cart', _routes.add_to_cart, ['POST']),
            ('/cart', 'cart', _routes.cart, ['GET']),
            ('/update_cart/<int:item_id>', 'update_cart', _routes.update_cart, ['POST']),
            ('/remove_from_cart/<int:item_id>', 'remove_from_cart', _routes.remove_from_cart, ['GET']),
        ]
        for rule, endpoint, viewfn, methods in aliases:
            # Only add if an endpoint with this name doesn't already exist
            if endpoint not in app.view_functions:
                app.add_url_rule(rule, endpoint=endpoint, view_func=viewfn, methods=methods)
    except Exception:
        pass

    # Seed data on first request
    try:
        from .routes import ensure_seed  # type: ignore

        @app.before_first_request
        def _ensure_seed():
            ensure_seed()
    except Exception:
        pass

    # Ensure instance folders exist
    try:
        os.makedirs(app.instance_path, exist_ok=True)
    except Exception:
        pass

    # Create DB tables and optionally seed an admin user from env
    with app.app_context():
        try:
            db.create_all()
        except Exception:
            pass
        # Ensure new profile columns exist for User table (SQLite fallback without running migrations)
        try:
            from sqlalchemy import text
            cols = db.session.execute(text("PRAGMA table_info('user')")).fetchall()  # type: ignore
            existing = {row[1] for row in cols}
            to_add = []
            if 'email' not in existing:
                to_add.append("ALTER TABLE user ADD COLUMN email VARCHAR(120)")
            if 'bio' not in existing:
                to_add.append("ALTER TABLE user ADD COLUMN bio TEXT")
            if 'avatar' not in existing:
                to_add.append("ALTER TABLE user ADD COLUMN avatar VARCHAR(256)")
            for stmt in to_add:
                try:
                    db.session.execute(text(stmt))
                except Exception:
                    pass
            if to_add:
                db.session.commit()
        except Exception:
            try:
                db.session.rollback()
            except Exception:
                pass
        # Seed products from data/products.json if empty
        try:
            from .utils import seed_db_from_json  # type: ignore
            # seed only if Product table empty
            from .models import Product  # type: ignore
            if Product.query.count() == 0:
                seed_db_from_json()
        except Exception:
            pass
        # If ADMIN_PASSWORD env var is set and there's no admin user, create one
        admin_pw = os.environ.get('ADMIN_PASSWORD')
        if admin_pw:
            try:
                from .models import User  # type: ignore
                if not User.query.filter_by(username='admin').first():
                    u = User(username='admin')
                    u.set_password(admin_pw)
                    u.is_admin = True
                    db.session.add(u)
                    db.session.commit()
            except Exception:
                # Don't fail app startup on seeding problems
                pass
        # Ensure avatars directory exists
        try:
            os.makedirs(os.path.join(static_folder, 'images', 'avatars') if (static_folder := app.static_folder) else os.path.join('static','images','avatars'), exist_ok=True)  # type: ignore
        except Exception:
            pass

    return app


# Convenience exports for legacy imports in tests and scripts
from .extensions import db  # type: ignore
from .models import User, Product  # type: ignore

__all__ = ["create_app", "db", "User", "Product"]

# Provide a convenience app instance for scripts/tests that expect `from app import app`
try:
    app = create_app()
except Exception:
    app = None
else:
    # bind db to module-level app to allow tests that call db.create_all() without context
    try:
        from .extensions import db  # type: ignore
        db.app = app
        # monkey-patch db.create_all() and db.drop_all() to work without active app context
        try:
            orig_create_all = db.create_all
            from flask import has_app_context

            def _wrapped_create_all(*a, **kw):
                # If an app context is already active, call directly; otherwise push a context for the call.
                if has_app_context():
                    return orig_create_all(*a, **kw)
                with app.app_context():
                    return orig_create_all(*a, **kw)

            db.create_all = _wrapped_create_all
        except Exception:
            pass
        try:
            orig_drop_all = db.drop_all
            from flask import has_app_context as _has_app_context

            def _wrapped_drop_all(*a, **kw):
                if _has_app_context():
                    return orig_drop_all(*a, **kw)
                with app.app_context():
                    return orig_drop_all(*a, **kw)

            db.drop_all = _wrapped_drop_all
        except Exception:
            pass
    except Exception:
        pass
    # Note: Do not push a permanent global app context here. The wrapped create_all/drop_all
    # functions will temporarily create a context when needed which keeps test isolation cleaner.
    try:
        # Some tests and simple scripts access `db.session` or `Model.query` at import time.
        # To improve ergonomics for this educational project, push a module-level app context.
        # This mirrors many tutorials and keeps tests simple.
        app.app_context().push()
    except Exception:
        pass
