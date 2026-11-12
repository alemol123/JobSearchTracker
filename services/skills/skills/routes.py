"""Skills JSON API. Routes only read the request, call logic/repository, and return JSON.

Skills never imports pipeline code. The two facts it needs from pipeline (which
applications are active, does an application exist) come over HTTP through
skills/pipeline_client.py (ADR-6).
"""

from flask import Blueprint, current_app, jsonify, request

from db import get_db
from skills import logic, pipeline_client
from skills import repository as repo

bp = Blueprint("skills", __name__, url_prefix="/skills")
# Second blueprint: the skills tagged on an application. The URLs start with
# /applications, but the data (application_skills) belongs to this service.
app_bp = Blueprint("application_skills", __name__, url_prefix="/applications")


def _text(value):
    """logic expects form-like strings: turn numbers and null into text."""
    return "" if value is None else str(value)


@bp.get("")
def list_skills():
    """All skills, archived included; the UI shows the archived ones separately."""
    return jsonify(skills=repo.list_skills(get_db(), include_archived=True),
                   max_level=logic.MAX_PROFICIENCY)


@bp.post("")
def add():
    body = request.get_json(silent=True) or {}
    data, errors = logic.parse_skill_form({k: _text(v) for k, v in body.items()})
    if errors:
        return jsonify(errors=errors), 400
    try:
        skill_id = repo.add_skill(get_db(), data["name"], data["category"])
    except ValueError as error:          # name already exists
        return jsonify(error=str(error)), 409
    return jsonify(id=skill_id), 201


@bp.put("/<int:skill_id>/proficiency")
def set_proficiency(skill_id):
    body = request.get_json(silent=True) or {}
    level, error = logic.parse_proficiency(_text(body.get("level")))
    if error:
        return jsonify(error=error), 400
    if level is None:                    # blank level = I don't have this skill
        repo.remove_my_skill(get_db(), skill_id)
        return jsonify(ok=True)
    try:
        repo.set_proficiency(get_db(), skill_id, level)
    except LookupError:
        return jsonify(error="Skill not found"), 404
    return jsonify(ok=True)


@bp.post("/<int:skill_id>/archive")
def archive(skill_id):
    try:
        repo.archive_skill(get_db(), skill_id)
    except LookupError:
        return jsonify(error="Skill not found"), 404
    return jsonify(ok=True)


@bp.get("/gap")
def gap():
    """The cross-seam flow: needs active IDs from pipeline, degrades if pipeline is down."""
    conn = get_db()
    tags, my_skills = repo.get_tags(conn), repo.get_my_skills(conn)
    names = repo.get_skill_names(conn)
    try:
        active_ids = pipeline_client.get_active_application_ids()
    except pipeline_client.PipelineUnavailable as error:
        current_app.logger.warning("pipeline unavailable for /skills/gap: %s", error)
        return jsonify(pipeline_available=False, priorities=[], missing=[],
                       notice="The application pipeline is unavailable, so the skill gap "
                              "can't be ranked right now. Your skills list still works.")
    priorities = logic.priority_scores(tags, my_skills, active_ids)
    missing = logic.rank_by_demand(tags, my_skills, active_ids)
    for row in priorities + missing:
        row["name"] = names.get(row["skill_id"])
    return jsonify(pipeline_available=True, priorities=priorities, missing=missing)


@app_bp.get("/<int:app_id>/skills")
def application_skills(app_id):
    """Tags only, no pipeline call: the UI loads the application header from pipeline
    separately, so the tags still show when pipeline is down."""
    conn = get_db()
    tagged = repo.get_skills_for_application(conn, app_id)
    tagged_ids = {s["id"] for s in tagged}
    available = [s for s in repo.list_skills(conn) if s["id"] not in tagged_ids]
    return jsonify(tagged=tagged, available=available)


@app_bp.post("/<int:app_id>/skills")
def tag(app_id):
    # Replaces the foreign key lost in the split (ADR-7). Fails closed: if we can't
    # check the application exists, we don't tag.
    try:
        if not pipeline_client.application_exists(app_id):
            return jsonify(error="Application not found"), 404
    except pipeline_client.PipelineUnavailable as error:
        current_app.logger.warning("pipeline unavailable for tagging: %s", error)
        return jsonify(error="Can't check the application right now. Try again in a minute."), 503
    body = request.get_json(silent=True) or {}
    try:
        repo.tag_application(get_db(), app_id, int(body.get("skill_id", 0)))
    except (LookupError, ValueError, TypeError) as error:
        return jsonify(error=str(error)), 400
    return jsonify(ok=True), 201


@app_bp.delete("/<int:app_id>/skills/<int:skill_id>")
def untag(app_id, skill_id):
    repo.untag_application(get_db(), app_id, skill_id)
    return jsonify(ok=True)
