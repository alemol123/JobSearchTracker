import pytest

from skills import repository as repo


def _application(conn, app_id):
    """application_skills references applications(id), so tests need a row to tag."""
    conn.execute(
        """INSERT INTO applications (id, company, role, source, date_applied)
           VALUES (?, 'Acme', 'Dev', 'referral', '2026-10-01')""",
        (app_id,),
    )
    return app_id


# ---------- skills: add / list / archive ----------

def test_add_skill_and_list_it(conn):
    skill_id = repo.add_skill(conn, "Python", "language")

    skills = repo.list_skills(conn)

    assert [(s["id"], s["name"], s["category"]) for s in skills] == [(skill_id, "Python", "language")]


def test_list_skills_is_sorted_by_name_ignoring_case(conn):
    for name in ["sql", "Docker", "python"]:
        repo.add_skill(conn, name, None)

    assert [s["name"] for s in repo.list_skills(conn)] == ["Docker", "python", "sql"]


def test_adding_an_existing_skill_name_is_an_error(conn):
    repo.add_skill(conn, "Python", None)

    with pytest.raises(ValueError, match="already exists"):
        repo.add_skill(conn, "python", None)   # names are case-insensitive


def test_archived_skill_is_hidden_from_default_list(conn):
    skill_id = repo.add_skill(conn, "Perl", None)

    repo.archive_skill(conn, skill_id)

    assert repo.list_skills(conn) == []
    assert [s["name"] for s in repo.list_skills(conn, include_archived=True)] == ["Perl"]


def test_adding_an_archived_skill_again_restores_it(conn):
    skill_id = repo.add_skill(conn, "Perl", None)
    repo.archive_skill(conn, skill_id)

    restored_id = repo.add_skill(conn, "Perl", None)

    assert restored_id == skill_id
    assert [s["name"] for s in repo.list_skills(conn)] == ["Perl"]


def test_archive_missing_skill_raises_lookup_error(conn):
    with pytest.raises(LookupError):
        repo.archive_skill(conn, 999)


# ---------- my_skills: proficiency ----------

def test_set_proficiency_inserts_then_updates(conn):
    skill_id = repo.add_skill(conn, "Python", None)

    repo.set_proficiency(conn, skill_id, 2)
    repo.set_proficiency(conn, skill_id, 4)

    assert repo.get_my_skills(conn) == {skill_id: 4}
    assert repo.list_skills(conn)[0]["proficiency_level"] == 4


def test_skill_i_do_not_have_shows_no_proficiency(conn):
    repo.add_skill(conn, "Rust", None)

    assert repo.list_skills(conn)[0]["proficiency_level"] is None


def test_remove_my_skill(conn):
    skill_id = repo.add_skill(conn, "Python", None)
    repo.set_proficiency(conn, skill_id, 3)

    repo.remove_my_skill(conn, skill_id)

    assert repo.get_my_skills(conn) == {}


# ---------- application_skills: tagging ----------

def test_tag_and_untag_application(conn):
    app_id = _application(conn, 1)
    python = repo.add_skill(conn, "Python", None)
    sql = repo.add_skill(conn, "SQL", None)

    repo.tag_application(conn, app_id, python)
    repo.tag_application(conn, app_id, sql)
    repo.untag_application(conn, app_id, sql)

    assert repo.get_tags(conn) == [(app_id, python)]
    assert [s["name"] for s in repo.get_skills_for_application(conn, app_id)] == ["Python"]


def test_tagging_the_same_skill_twice_keeps_one_tag(conn):
    app_id = _application(conn, 1)
    python = repo.add_skill(conn, "Python", None)

    repo.tag_application(conn, app_id, python)
    repo.tag_application(conn, app_id, python)

    assert repo.get_tags(conn) == [(app_id, python)]


def test_archived_skill_cannot_be_newly_tagged(conn):
    app_id = _application(conn, 1)
    perl = repo.add_skill(conn, "Perl", None)
    repo.archive_skill(conn, perl)

    with pytest.raises(ValueError, match="archived"):
        repo.tag_application(conn, app_id, perl)


def test_tagging_a_missing_skill_raises_lookup_error(conn):
    app_id = _application(conn, 1)

    with pytest.raises(LookupError):
        repo.tag_application(conn, app_id, 999)


def test_archiving_keeps_existing_tags_and_proficiency(conn):
    # Soft delete: history is preserved, the skill is only hidden from new tagging.
    app_id = _application(conn, 1)
    perl = repo.add_skill(conn, "Perl", None)
    repo.tag_application(conn, app_id, perl)
    repo.set_proficiency(conn, perl, 2)

    repo.archive_skill(conn, perl)

    assert repo.get_tags(conn) == [(app_id, perl)]
    assert repo.get_my_skills(conn) == {perl: 2}
    assert repo.get_skills_for_application(conn, app_id)[0]["archived"] == 1


def test_skill_names_include_archived_skills(conn):
    python = repo.add_skill(conn, "Python", None)
    perl = repo.add_skill(conn, "Perl", None)
    repo.archive_skill(conn, perl)

    assert repo.get_skill_names(conn) == {python: "Python", perl: "Perl"}


def test_set_proficiency_on_missing_skill_raises_lookup_error(conn):
    with pytest.raises(LookupError):
        repo.set_proficiency(conn, 999, 3)
