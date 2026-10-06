import os
from flask import Flask, redirect, url_for

from db import close_db, db_path, init_db
from pipeline.routes import bp as pipeline_bp
from skills.routes import bp as skills_bp


def create_app():
    app = Flask(__name__)
    app.config["DATA_DIR"] = os.environ.get("DATA_DIR", "./data")
    app.config["STALE_DAYS"] = int(os.environ.get("STALE_DAYS", "14"))
    # Signs the cookie that carries flash messages. Single-user local app, so a default is fine.
    app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev-only-change-me")
    os.makedirs(app.config["DATA_DIR"], exist_ok=True)

    app.config["DATABASE"] = db_path(app.config["DATA_DIR"])
    init_db(app.config["DATABASE"])
    app.teardown_appcontext(close_db)

    app.register_blueprint(pipeline_bp)
    app.register_blueprint(skills_bp)

    @app.route("/")
    def index():
        return redirect(url_for("pipeline.list_view"))

    return app


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8000"))
    create_app().run(host="0.0.0.0", port=port)
