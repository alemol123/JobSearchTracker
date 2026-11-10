import os

from flask import Flask

from db import close_db
from skills.routes import bp as skills_bp


def get_port():
    return int(os.environ.get("PORT", "8000"))


def create_app():
    app = Flask(__name__)
    app.teardown_appcontext(close_db)

    app.register_blueprint(skills_bp)

    return app


if __name__ == "__main__":
    create_app().run(host="0.0.0.0", port=get_port())
