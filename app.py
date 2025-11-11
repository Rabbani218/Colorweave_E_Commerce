"""ColorWeave application starter.

A production-friendly entrypoint that:
- builds the Flask app via the factory
- supports HOST/PORT/DEBUG envs
- optionally applies DB migrations
- optionally warms AI embedding/vision indices for snappy first requests
"""
import os
import logging
from contextlib import suppress

from app import create_app


def _bool_env(name: str, default: bool = False) -> bool:
    val = os.environ.get(name)
    if val is None:
        return default
    return str(val).strip().lower() in {"1", "true", "yes", "on"}


def configure_logging():
    level = os.environ.get("LOG_LEVEL", "INFO").upper()
    logging.basicConfig(
        level=getattr(logging, level, logging.INFO),
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    )


def maybe_apply_migrations(app):
    if not _bool_env("APPLY_MIGRATIONS", False):
        return
    try:
        from flask_migrate import upgrade  # type: ignore
        with app.app_context():
            upgrade()
        logging.getLogger(__name__).info("Applied database migrations (upgrade)")
    except Exception as e:
        logging.getLogger(__name__).warning("Skipping migrations: %s", e)


def maybe_warm_ai(app):
    if not _bool_env("AI_WARM", True):  # enabled by default
        return
    try:
        with app.app_context():
            # Warm text embeddings
            try:
                from app.ai.embeddings import EmbeddingIndexer  # type: ignore
                from pathlib import Path
                persist_dir = Path("data") / "ai_index"
                idx = EmbeddingIndexer(persist_dir=str(persist_dir))
                idx.build_index(force=False)
                logging.getLogger(__name__).info("Embedding index warmed: %d items", len(idx.ids))
            except Exception as e:
                logging.getLogger(__name__).warning("Embedding warm failed: %s", e)

            # Warm vision features
            try:
                from app.ai.vision import VisionIndexer  # type: ignore
                static_folder = app.static_folder or "static"
                persist_dir = os.path.join("data", "ai_index")
                v = VisionIndexer(static_folder=static_folder, persist_dir=persist_dir)
                v.build_index(force=False)
                logging.getLogger(__name__).info("Vision index warmed: %d items", len(v.ids))
            except Exception as e:
                logging.getLogger(__name__).warning("Vision warm failed: %s", e)
    except Exception as e:
        logging.getLogger(__name__).warning("AI warm sequence skipped: %s", e)


def main():
    configure_logging()
    app = create_app()
    maybe_apply_migrations(app)
    maybe_warm_ai(app)

    host = os.environ.get("HOST") or os.environ.get("FLASK_RUN_HOST") or "127.0.0.1"
    port = int(os.environ.get("PORT") or os.environ.get("FLASK_RUN_PORT") or 5001)
    debug = _bool_env("DEBUG", _bool_env("FLASK_DEBUG", False))

    # Optional ngrok tunneling for development / demo
    if _bool_env("USE_NGROK", False):
        with suppress(Exception):
            from pyngrok import ngrok
            authtoken = os.environ.get("NGROK_AUTHTOKEN")
            if authtoken:
                ngrok.set_auth_token(authtoken)
            region = os.environ.get("NGROK_REGION") or "ap"  # default to Asia/Pacific for latency
            public_url = ngrok.connect(addr=port, proto="http", region=region).public_url
            logging.getLogger(__name__).info("ngrok tunnel active: %s -> http://%s:%s", public_url, host, port)

    logging.getLogger(__name__).info("Starting ColorWeave on http://%s:%s (debug=%s)", host, port, debug)
    app.run(host=host, port=port, debug=debug, threaded=True, use_reloader=debug)


if __name__ == "__main__":
    main()
