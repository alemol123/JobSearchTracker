"""Pipeline data access. SQL only; the rules live in pipeline/logic.py.

Every function takes an open sqlite3 connection as its first argument,
so tests can pass in a temporary database.
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
    app["stage_entered_on"] = datetime.fromisoformat(app["stage_entered_at"]).date()
    return app


def create_application(conn, data):
    """Insert a new application in stage 'applied' and record that in stage_history."""
    cur = conn.execute(
        """INSERT INTO applications
               (company, role, source, date_applied, salary_range_min, salary_range_max)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (data["company"], data["role"], data["source"], data["date_applied"].isoformat(),
         data["salary_range_min"], data["salary_range_max"]),
    )
    app_id = cur.lastrowid
    # It entered 'applied' on the day it was applied for, not the day it was typed in.
    entered_at = datetime.combine(data["date_applied"], datetime.min.time())
    conn.execute(
        "INSERT INTO stage_history (application_id, stage, entered_at) VALUES (?, 'applied', ?)",
        (app_id, entered_at.isoformat()),
    )
    conn.commit()
    return app_id


def list_applications(conn):
    rows = conn.execute(_SELECT_APPLICATIONS + " ORDER BY a.date_applied DESC, a.id DESC")
    return [_to_dict(r) for r in rows]


def get_application(conn, app_id):
    row = conn.execute(_SELECT_APPLICATIONS + " WHERE a.id = ?", (app_id,)).fetchone()
    return _to_dict(row) if row else None


def get_stage_history(conn, app_id):
    rows = conn.execute(
        "SELECT stage, entered_at FROM stage_history WHERE application_id = ? ORDER BY entered_at, id",
        (app_id,),
    )
    return [dict(r) for r in rows]


def change_stage(conn, app_id, new_stage, now=None):
    """Validate and apply a stage change. Raises LookupError or InvalidTransition."""
    row = conn.execute("SELECT current_stage FROM applications WHERE id = ?", (app_id,)).fetchone()
    if row is None:
        raise LookupError(f"Application {app_id} not found")

    validate_transition(row["current_stage"], new_stage)   # raises before anything is written

    now = now or datetime.now()
    conn.execute(
        "INSERT INTO stage_history (application_id, stage, entered_at) VALUES (?, ?, ?)",
        (app_id, new_stage, now.isoformat(timespec="seconds")),
    )
    conn.execute(
        "UPDATE applications SET current_stage = ?, status = ? WHERE id = ?",
        (new_stage, status_for_stage(new_stage), app_id),
    )
    conn.commit()


def get_active_application_ids(conn):
    """The seam used by the skills domain: which applications still count."""
    rows = conn.execute("SELECT id FROM applications WHERE status = 'active'")
    return {r["id"] for r in rows}


def get_stage_histories_with_source(conn):
    """Input for logic.conversion_rates_by_source: [{"source", "stages"}, ...]."""
    rows = conn.execute(
        """SELECT a.id, a.source, h.stage
             FROM applications a JOIN stage_history h ON h.application_id = a.id
            ORDER BY a.id, h.entered_at, h.id"""
    )
    histories = {}
    for r in rows:
        histories.setdefault(r["id"], {"source": r["source"], "stages": []})
        histories[r["id"]]["stages"].append(r["stage"])
    return list(histories.values())
