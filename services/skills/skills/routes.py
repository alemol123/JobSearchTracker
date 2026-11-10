"""Skill gap pages. Routes only read the form, call logic/repository, and redirect.

Dependency goes one way: skills may call the pipeline's repository functions
(which would become HTTP calls after a split), but pipeline never imports skills.
"""

from flask import Blueprint, abort, flash, redirect, render_template, request, url_for

from db import get_db
from pipeline import repository as pipeline_repo
from skills import logic
from skills import repository as repo

bp = Blueprint("skills", __name__, url_prefix="/skills")


@bp.get("/")
def list_view():
    conn = get_db()
    all_skills = repo.list_skills(conn, include_archived=True)
    return render_template("skills/list.html",
                           skills=[s for s in all_skills if not s["archived"]],
                           archived=[s for s in all_skills if s["archived"]],
                           max_level=logic.MAX_PROFICIENCY)


@bp.post("/")
def add():
    data, errors = logic.parse_skill_form(request.form)
    if not errors:
        try:
            repo.add_skill(get_db(), data["name"], data["category"])
            flash("Skill added.")
        except ValueError as error:          # name already exists
            errors.append(str(error))
    for error in errors:
        flash(error, "error")
    return redirect(url_for("skills.list_view"))


@bp.post("/<int:skill_id>/proficiency")
def set_proficiency(skill_id):
    level, error = logic.parse_proficiency(request.form.get("level", ""))
    if error:
        flash(error, "error")
    elif level is None:
        repo.remove_my_skill(get_db(), skill_id)
        flash("Removed from my skills.")
    else:
        try:
            repo.set_proficiency(get_db(), skill_id, level)
        except LookupError:
            abort(404)
        flash("Proficiency saved.")
    return redirect(url_for("skills.list_view"))


@bp.post("/<int:skill_id>/archive")
def archive(skill_id):
    try:
        repo.archive_skill(get_db(), skill_id)
    except LookupError:
        abort(404)
    flash("Skill archived. Existing tags are kept, but it can't be added to new applications.")
    return redirect(url_for("skills.list_view"))


@bp.get("/gap")
def gap():
    conn = get_db()
    tags = repo.get_tags(conn)
    my_skills = repo.get_my_skills(conn)
    active_ids = pipeline_repo.get_active_application_ids(conn)   # the seam (ADR-2)
    return render_template("skills/gap.html",
                           priorities=logic.priority_scores(tags, my_skills, active_ids),
                           missing=logic.rank_by_demand(tags, my_skills, active_ids),
                           names=repo.get_skill_names(conn))


@bp.get("/applications/<int:app_id>")
def application_skills(app_id):
    conn = get_db()
    application = pipeline_repo.get_application(conn, app_id)
    if application is None:
        abort(404)
    tagged = repo.get_skills_for_application(conn, app_id)
    tagged_ids = {s["id"] for s in tagged}
    available = [s for s in repo.list_skills(conn) if s["id"] not in tagged_ids]
    return render_template("skills/application.html", application=application,
                           tagged=tagged, available=available)


@bp.post("/applications/<int:app_id>/tag")
def tag(app_id):
    try:
        repo.tag_application(get_db(), app_id, request.form.get("skill_id", type=int))
        flash("Skill added to application.")
    except (LookupError, ValueError) as error:
        flash(str(error), "error")
    return redirect(url_for("skills.application_skills", app_id=app_id))


@bp.post("/applications/<int:app_id>/untag")
def untag(app_id):
    repo.untag_application(get_db(), app_id, request.form.get("skill_id", type=int))
    flash("Skill removed from application.")
    return redirect(url_for("skills.application_skills", app_id=app_id))
