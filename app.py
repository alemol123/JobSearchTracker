import os
from flask import Flask, render_template

from db import close_db, db_path, init_db


def create_app():
    app = Flask(__name__)
    app.config["DATA_DIR"] = os.environ.get("DATA_DIR", "./data")
    app.config["STALE_DAYS"] = int(os.environ.get("STALE_DAYS", "14"))
    os.makedirs(app.config["DATA_DIR"], exist_ok=True)

    app.config["DATABASE"] = db_path(app.config["DATA_DIR"])
    init_db(app.config["DATABASE"])
    app.teardown_appcontext(close_db)

    @app.route("/")
    def index():
        return render_template("base.html")

    return app


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8000"))
    create_app().run(host="0.0.0.0", port=port)
