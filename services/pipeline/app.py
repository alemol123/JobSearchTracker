import os

from flask import Flask

from db import close_db
from pipeline.routes import bp as pipeline_bp


def get_port():
    return int(os.environ.get("PORT", "8000"))


def create_app():
    app = Flask(__name__)
    app.config["STALE_DAYS"] = int(os.environ.get("STALE_DAYS", "14"))
    app.teardown_appcontext(close_db)

    app.register_blueprint(pipeline_bp)

    return app


if __name__ == "__main__":
    create_app().run(host="0.0.0.0", port=get_port())
