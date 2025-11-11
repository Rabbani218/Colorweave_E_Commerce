from flask_sqlalchemy import SQLAlchemy  # type: ignore
from flask_migrate import Migrate  # type: ignore
from flask_login import LoginManager  # type: ignore
from flask_session import Session as FlaskSession  # type: ignore

db = SQLAlchemy()
migrate = Migrate()
login_manager = LoginManager()
flask_session = FlaskSession()
