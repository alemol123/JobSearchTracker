import logging
import os
import sys
import time

import pymssql
from flask import Flask, g, jsonify, request
from werkzeug.exceptions import HTTPException

from db import close_db, connect
from skills.routes import app_bp as application_skills_bp
from skills.routes import bp as skills_bp

# Logs go to stdout so `docker compose logs` and Azure's log stream show them.
logging.basicConfig(level=logging.INFO, stream=sys.stdout,
                    format="%(asctime)s %(levelname)s %(message)s")


def get_port():
    return int(os.environ.get("PORT", "8000"))


def create_app():
    app = Flask(__name__)
    app.teardown_appcontext(close_db)       # close each request's DB connection at the end

    app.register_blueprint(skills_bp)
    app.register_blueprint(application_skills_bp)

    @app.before_request
    def start_timer():
        g.started = time.perf_counter()

    @app.after_request
    def log_and_cors(response):
        # One line per request: method, path, status, duration.
        ms = (time.perf_counter() - g.get("started", time.perf_counter())) * 1000
        app.logger.info("%s %s %s %.0fms", request.method, request.path, response.status_code, ms)
        # CORS: only the UI's origin may call this API from a browser; any other origin gets no headers.
        allowed = os.environ.get("ALLOWED_ORIGIN", "http://localhost:8080")
        if request.headers.get("Origin") == allowed:
            response.headers["Access-Control-Allow-Origin"] = allowed
            response.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, DELETE, OPTIONS"
            response.headers["Access-Control-Allow-Headers"] = "Content-Type"
            response.headers["Vary"] = "Origin"
        return response

    @app.get("/health")
    def health():
        """Proves this service can write to its own database. Never calls pipeline."""
        version = os.environ.get("GIT_SHA", "unknown")
        conn = None
        try:
            conn = connect()                # no long retry: health must answer quickly
            cur = conn.cursor()
            cur.execute("INSERT INTO health_check DEFAULT VALUES")              # write
            cur.execute("SELECT TOP 1 id FROM health_check ORDER BY id DESC")  # read
            cur.fetchone()
            conn.rollback()                 # leave nothing behind
        except pymssql.Error as error:      # any DB problem: can't connect, can't write, ...
            app.logger.warning("health check failed: %s", error)
            return jsonify(status="error", db="unavailable", version=version), 503
        finally:
            if conn is not None:
                conn.close()
        return jsonify(status="ok", db="ok", version=version), 200

    # JSON errors, never HTML pages or stack traces.
    @app.errorhandler(HTTPException)
    def http_error(error):                  # 404, 405, 400 ...
        return jsonify(error=error.description), error.code

    @app.errorhandler(Exception)
    def server_error(error):                # anything unexpected: log it, answer 500
        app.logger.exception("unhandled error")
        return jsonify(error="Internal error"), 500

    return app


if __name__ == "__main__":
    create_app().run(host="0.0.0.0", port=get_port())
