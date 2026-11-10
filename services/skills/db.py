import logging
import os
import time
from urllib.parse import unquote, urlparse

import pymssql
from flask import g

log = logging.getLogger(__name__)


def connect():
    """Open one connection from DATABASE_URL, e.g. mssql://user:pw@host:1433/dbname."""
    url = urlparse(os.environ["DATABASE_URL"])
    return pymssql.connect(
        server=url.hostname,
        port=url.port or 1433,
        user=unquote(url.username),
        password=unquote(url.password),
        database=url.path.lstrip("/"),
        as_dict=True,          # rows come back as dicts: row["company"]
        login_timeout=15,
    )


def connect_with_retry(attempts=8, first_wait=2):
    """Retry with exponential backoff: a paused Azure SQL database takes up to a minute
    to resume and refuses connections meanwhile (error 40613)."""
    wait = first_wait
    for attempt in range(1, attempts + 1):
        try:
            return connect()
        except pymssql.OperationalError as error:
            if attempt == attempts:
                raise
            log.warning("DB connect failed (attempt %s/%s): %s; retrying in %ss",
                        attempt, attempts, error, wait)
            time.sleep(wait)
            wait = min(wait * 2, 30)


def get_db():
    # One connection per request, reused if asked for twice in the same request.
    if "db" not in g:
        g.db = connect_with_retry()
    return g.db


def close_db(exception=None):
    conn = g.pop("db", None)
    if conn is not None:
        conn.close()
