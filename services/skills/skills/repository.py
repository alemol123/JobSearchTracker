"""Skills data access. SQL only; the rules live in skills/logic.py.

Every function takes an open pymssql connection (as_dict=True) as its first argument.
Never reads the applications table (ADR-2): it lives in the pipeline database, so
application IDs are plain numbers and which ones are active comes from the pipeline service.
"""


def add_skill(conn, name, category):
    """Create a skill. Re-adding an archived skill's name restores it instead."""
    cur = conn.cursor()
    cur.execute("SELECT id, archived FROM skills WHERE name = %s", (name,))
    existing = cur.fetchone()
    if existing is not None:
        if not existing["archived"]:
            raise ValueError(f"Skill '{name}' already exists.")
        cur.execute("UPDATE skills SET archived = 0 WHERE id = %s", (existing["id"],))
        conn.commit()
        return existing["id"]

    # OUTPUT INSERTED.id returns the new IDENTITY value as a result row (SQL Server has no lastrowid).
    cur.execute(
        "INSERT INTO skills (name, category) OUTPUT INSERTED.id VALUES (%s, %s)",
        (name, category),
    )
    skill_id = cur.fetchone()["id"]
    conn.commit()
    return skill_id


def archive_skill(conn, skill_id):
    """Soft delete: hide from new tagging, keep existing tags and proficiency."""
    cur = conn.cursor()
    cur.execute("UPDATE skills SET archived = 1 WHERE id = %s", (skill_id,))
    if cur.rowcount == 0:
        raise LookupError(f"Skill {skill_id} not found")
    conn.commit()


def list_skills(conn, include_archived=False):
    """Skills sorted by name, each with my proficiency_level (None if I don't have it)."""
    sql = """SELECT s.id, s.name, s.category, s.archived, m.proficiency_level
               FROM skills s LEFT JOIN my_skills m ON m.skill_id = s.id"""
    if not include_archived:
        sql += " WHERE s.archived = 0"
    sql += " ORDER BY s.name"   # SQL Server's default collation already ignores case
    cur = conn.cursor()
    cur.execute(sql)
    return cur.fetchall()


def get_skill_names(conn):
    """{skill_id: name} for every skill, archived included (for showing results)."""
    cur = conn.cursor()
    cur.execute("SELECT id, name FROM skills")
    return {r["id"]: r["name"] for r in cur.fetchall()}


def set_proficiency(conn, skill_id, level):
    """Insert or update my level for a skill (1-5; the table's CHECK enforces it)."""
    cur = conn.cursor()
    cur.execute("SELECT 1 AS found FROM skills WHERE id = %s", (skill_id,))
    if cur.fetchone() is None:
        raise LookupError(f"Skill {skill_id} not found")
    # Upsert: try the UPDATE first; if it changed no row, the skill isn't in my_skills yet.
    cur.execute(
        """UPDATE my_skills SET proficiency_level = %s WHERE skill_id = %s;
           IF @@ROWCOUNT = 0
               INSERT INTO my_skills (skill_id, proficiency_level) VALUES (%s, %s);""",
        (level, skill_id, skill_id, level),
    )
    conn.commit()


def remove_my_skill(conn, skill_id):
    cur = conn.cursor()
    cur.execute("DELETE FROM my_skills WHERE skill_id = %s", (skill_id,))
    conn.commit()


def get_my_skills(conn):
    """{skill_id: proficiency_level} — the shape skills.logic expects."""
    cur = conn.cursor()
    cur.execute("SELECT skill_id, proficiency_level FROM my_skills")
    return {r["skill_id"]: r["proficiency_level"] for r in cur.fetchall()}


def tag_application(conn, application_id, skill_id):
    """Mark a skill as required by an application. Archived skills can't be newly tagged."""
    cur = conn.cursor()
    cur.execute("SELECT archived FROM skills WHERE id = %s", (skill_id,))
    skill = cur.fetchone()
    if skill is None:
        raise LookupError(f"Skill {skill_id} not found")
    if skill["archived"]:
        raise ValueError("This skill is archived and can't be added to applications.")
    # Tagging the same skill twice is a no-op instead of a primary key error.
    cur.execute(
        """IF NOT EXISTS (SELECT 1 FROM application_skills
                           WHERE application_id = %s AND skill_id = %s)
               INSERT INTO application_skills (application_id, skill_id) VALUES (%s, %s);""",
        (application_id, skill_id, application_id, skill_id),
    )
    conn.commit()


def untag_application(conn, application_id, skill_id):
    cur = conn.cursor()
    cur.execute(
        "DELETE FROM application_skills WHERE application_id = %s AND skill_id = %s",
        (application_id, skill_id),
    )
    conn.commit()


def get_tags(conn):
    """Every (application_id, skill_id) pair — the 'tags' input of skills.logic."""
    cur = conn.cursor()
    cur.execute(
        "SELECT application_id, skill_id FROM application_skills ORDER BY application_id, skill_id"
    )
    return [(r["application_id"], r["skill_id"]) for r in cur.fetchall()]


def get_skills_for_application(conn, application_id):
    """Skills tagged on one application, archived ones included (they are history)."""
    cur = conn.cursor()
    cur.execute(
        """SELECT s.id, s.name, s.archived
             FROM application_skills a JOIN skills s ON s.id = a.skill_id
            WHERE a.application_id = %s
            ORDER BY s.name""",
        (application_id,),
    )
    return cur.fetchall()
