"""Skills data access. SQL only; the rules live in skills/logic.py.

Never reads the applications table (ADR-2): application IDs are treated as
plain numbers, and which ones are active comes from the pipeline domain.
"""


def add_skill(conn, name, category):
    """Create a skill. Re-adding an archived skill's name restores it instead."""
    existing = conn.execute("SELECT id, archived FROM skills WHERE name = ?", (name,)).fetchone()
    if existing is not None:
        if not existing["archived"]:
            raise ValueError(f"Skill '{name}' already exists.")
        conn.execute("UPDATE skills SET archived = 0 WHERE id = ?", (existing["id"],))
        conn.commit()
        return existing["id"]

    cur = conn.execute("INSERT INTO skills (name, category) VALUES (?, ?)", (name, category))
    conn.commit()
    return cur.lastrowid


def archive_skill(conn, skill_id):
    """Soft delete: hide from new tagging, keep existing tags and proficiency."""
    cur = conn.execute("UPDATE skills SET archived = 1 WHERE id = ?", (skill_id,))
    if cur.rowcount == 0:
        raise LookupError(f"Skill {skill_id} not found")
    conn.commit()


def list_skills(conn, include_archived=False):
    """Skills sorted by name, each with my proficiency_level (None if I don't have it)."""
    sql = """SELECT s.id, s.name, s.category, s.archived, m.proficiency_level
               FROM skills s LEFT JOIN my_skills m ON m.skill_id = s.id"""
    if not include_archived:
        sql += " WHERE s.archived = 0"
    sql += " ORDER BY s.name COLLATE NOCASE"
    return [dict(r) for r in conn.execute(sql)]


def get_skill_names(conn):
    """{skill_id: name} for every skill, archived included (for showing results)."""
    return {r["id"]: r["name"] for r in conn.execute("SELECT id, name FROM skills")}


def set_proficiency(conn, skill_id, level):
    """Insert or update my level for a skill (1-5; the table's CHECK enforces it)."""
    if conn.execute("SELECT 1 FROM skills WHERE id = ?", (skill_id,)).fetchone() is None:
        raise LookupError(f"Skill {skill_id} not found")
    conn.execute(
        """INSERT INTO my_skills (skill_id, proficiency_level) VALUES (?, ?)
           ON CONFLICT (skill_id) DO UPDATE SET proficiency_level = excluded.proficiency_level""",
        (skill_id, level),
    )
    conn.commit()


def remove_my_skill(conn, skill_id):
    conn.execute("DELETE FROM my_skills WHERE skill_id = ?", (skill_id,))
    conn.commit()


def get_my_skills(conn):
    """{skill_id: proficiency_level} — the shape skills.logic expects."""
    rows = conn.execute("SELECT skill_id, proficiency_level FROM my_skills")
    return {r["skill_id"]: r["proficiency_level"] for r in rows}


def tag_application(conn, application_id, skill_id):
    """Mark a skill as required by an application. Archived skills can't be newly tagged."""
    skill = conn.execute("SELECT archived FROM skills WHERE id = ?", (skill_id,)).fetchone()
    if skill is None:
        raise LookupError(f"Skill {skill_id} not found")
    if skill["archived"]:
        raise ValueError("This skill is archived and can't be added to applications.")
    # The composite primary key makes a duplicate tag a no-op.
    conn.execute(
        "INSERT OR IGNORE INTO application_skills (application_id, skill_id) VALUES (?, ?)",
        (application_id, skill_id),
    )
    conn.commit()


def untag_application(conn, application_id, skill_id):
    conn.execute(
        "DELETE FROM application_skills WHERE application_id = ? AND skill_id = ?",
        (application_id, skill_id),
    )
    conn.commit()


def get_tags(conn):
    """Every (application_id, skill_id) pair — the 'tags' input of skills.logic."""
    rows = conn.execute(
        "SELECT application_id, skill_id FROM application_skills ORDER BY application_id, skill_id"
    )
    return [(r["application_id"], r["skill_id"]) for r in rows]


def get_skills_for_application(conn, application_id):
    """Skills tagged on one application, archived ones included (they are history)."""
    rows = conn.execute(
        """SELECT s.id, s.name, s.archived
             FROM application_skills a JOIN skills s ON s.id = a.skill_id
            WHERE a.application_id = ?
            ORDER BY s.name COLLATE NOCASE""",
        (application_id,),
    )
    return [dict(r) for r in rows]
