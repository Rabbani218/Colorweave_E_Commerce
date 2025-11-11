import os


class Config:
    """Base configuration loaded from environment variables."""
    SECRET_KEY = os.environ.get('SECRET_KEY', 'dev-secret')
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL', 'sqlite:///data/app.db')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    MAX_CONTENT_LENGTH = int(os.environ.get('MAX_CONTENT_LENGTH', 5 * 1024 * 1024))
    SESSION_PERMANENT = False
    # Optional Redis session store
    REDIS_URL = os.environ.get('REDIS_URL')
    # Session backend: use redis if REDIS_URL provided, otherwise filesystem
    if REDIS_URL:
        SESSION_TYPE = 'redis'
        SESSION_PERMANENT = False
    else:
        SESSION_TYPE = 'filesystem'

    # AI configuration
    # AI_PROVIDER: 'local' (recommended) or 'openai' or 'replicate'
    AI_PROVIDER = os.environ.get('AI_PROVIDER', 'local')
    # For local embeddings we may use a model name if sentence-transformers is available
    EMBEDDING_MODEL = os.environ.get('EMBEDDING_MODEL', 'all-MiniLM-L6-v2')
    # Path to persist vector index / vector DB
    VECTOR_DB_PATH = os.environ.get('VECTOR_DB_PATH', os.path.join(os.path.dirname(__file__), 'data', 'ai_index'))
    # Image generation backend (e.g., 'local' for placeholder/local generation)
    IMAGE_BACKEND = os.environ.get('IMAGE_BACKEND', 'local')


class DevelopmentConfig(Config):
    DEBUG = True


class ProductionConfig(Config):
    DEBUG = False
