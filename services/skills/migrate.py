"""Apply migrations/NNN_*.sql in order, each exactly once. Run at container start."""
import glob
import logging
import os
import sys

from db import connect_with_retry

logging.basicConfig(level=logging.INFO, stream=sys.stdout,
                    format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("migrate")
HERE = os.path.dirname(os.path.abspath(__file__))


def batches(sql):
    """SQL Server needs separate batches for some DDL; split on lines that say GO."""
    parts, current = [], []
    for line in sql.splitlines():
        if line.strip().upper() == "GO":
            parts.append("\n".join(current))
            current = []
        else:
            current.append(line)
    parts.append("\n".join(current))
    return [p for p in parts if p.strip()]


def run(conn):
    cur = conn.cursor()
    cur.execute("""IF OBJECT_ID('schema_migrations') IS NULL
                   CREATE TABLE schema_migrations (
                       version    NVARCHAR(100) PRIMARY KEY,
                       applied_at DATETIME2 NOT NULL DEFAULT SYSUTCDATETIME())""")
    conn.commit()
    cur.execute("SELECT version FROM schema_migrations")
    done = {row["version"] for row in cur.fetchall()}
    for path in sorted(glob.glob(os.path.join(HERE, "migrations", "*.sql"))):
        version = os.path.basename(path)
        if version in done:
            continue
        try:
            with open(path) as f:
                for batch in batches(f.read()):
                    cur.execute(batch)
            cur.execute("INSERT INTO schema_migrations (version) VALUES (%s)", (version,))
            conn.commit()                    # the migration and its record commit together
            log.info("applied migration %s", version)
        except Exception:
            conn.rollback()
            log.exception("migration %s failed; nothing from it was kept", version)
            raise
    log.info("migrations up to date (%s applied before this run)", len(done))


if __name__ == "__main__":
    conn = connect_with_retry()
    run(conn)
    conn.close()
