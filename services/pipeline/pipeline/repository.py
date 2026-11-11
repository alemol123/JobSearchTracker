"""Pipeline data access. SQL only; the rules live in pipeline/logic.py.

Every function takes an open pymssql connection (as_dict=True) as its first
argument, so tests can pass in a connection to a test database.
"""

from datetime import datetime

from pipeline.logic import status_for_stage, validate_transition

# Each application row plus the time it entered its current stage
# (the newest stage_history row for that application).
_SELECT_APPLICATIONS = """
    SELECT a.*,
           (SELECT MAX(h.entered_at) FROM stage_history h
             WHERE h.application_id = a.id) AS stage_entered_at
      FROM applications a
"""


def _to_dict(row):
    app = dict(row)
    # DATETIME2 already comes back as a Python datetime, so no parsing is needed.
    app["stage_entered_on"] = app["stage_entered_at"].date()
    return app


def create_application(conn, data):
    """Insert a new application in stage 'applied' and record that in stage_history."""
    cur = conn.cursor()
    # OUTPUT INSERTED.id returns the new IDENTITY value as a result row (SQL Server has no lastrowid).
    cur.execute(
        """INSERT INTO applications
               (company, role, source, date_applied, salary_range_min, salary_range_max)
           OUTPUT INSERTED.id
           VALUES (%s, %s, %s, %s, %s, %s)""",
        (data["company"], data["role"], data["source"], data["date_applied"],
         data["salary_range_min"], data["salary_range_max"]),
    )
    app_id = cur.fetchone()["id"]
    # It entered 'applied' on the day it was applied for, not the day it was typed in.
    entered_at = datetime.combine(data["date_applied"], datetime.min.time())
    cur.execute(
        "INSERT INTO stage_history (application_id, stage, entered_at) VALUES (%s, 'applied', %s)",
        (app_id, entered_at),
    )
    conn.commit()   # both inserts are kept together or not at all
    return app_id


def list_applications(conn):
    cur = conn.cursor()
    cur.execute(_SELECT_APPLICATIONS + " ORDER BY a.date_applied DESC, a.id DESC")
    return [_to_dict(r) for r in cur.fetchall()]


def get_application(conn, app_id):
    cur = conn.cursor()
    cur.execute(_SELECT_APPLICATIONS + " WHERE a.id = %s", (app_id,))
    row = cur.fetchone()
    return _to_dict(row) if row else None


def get_stage_history(conn, app_id):
    cur = conn.cursor()
    cur.execute(
        "SELECT stage, entered_at FROM stage_history WHERE application_id = %s ORDER BY entered_at, id",
        (app_id,),
    )
    return cur.fetchall()


def change_stage(conn, app_id, new_stage, now=None):
    """Validate and apply a stage change. Raises LookupError or InvalidTransition."""
    cur = conn.cursor()
    cur.execute("SELECT current_stage FROM applications WHERE id = %s", (app_id,))
    row = cur.fetchone()
    if row is None:
        raise LookupError(f"Application {app_id} not found")

    validate_transition(row["current_stage"], new_stage)   # raises before anything is written

    now = (now or datetime.now()).replace(microsecond=0)    # the column is DATETIME2(0): whole seconds
    cur.execute(
        "INSERT INTO stage_history (application_id, stage, entered_at) VALUES (%s, %s, %s)",
        (app_id, new_stage, now),
    )
    cur.execute(
        "UPDATE applications SET current_stage = %s, status = %s WHERE id = %s",
        (new_stage, status_for_stage(new_stage), app_id),
    )
    conn.commit()   # history row and current_stage change together (ADR-3)


def get_active_application_ids(conn):
    """The seam used by the skills service (via GET /applications/active-ids)."""
    cur = conn.cursor()
    cur.execute("SELECT id FROM applications WHERE status = 'active'")
    return {r["id"] for r in cur.fetchall()}


def get_stage_histories_with_source(conn):
    """Input for logic.conversion_rates_by_source: [{"source", "stages"}, ...]."""
    cur = conn.cursor()
    cur.execute(
        """SELECT a.id, a.source, h.stage
             FROM applications a JOIN stage_history h ON h.application_id = a.id
            ORDER BY a.id, h.entered_at, h.id"""
    )
    histories = {}
    for r in cur.fetchall():
        histories.setdefault(r["id"], {"source": r["source"], "stages": []})
        histories[r["id"]]["stages"].append(r["stage"])
    return list(histories.values())
