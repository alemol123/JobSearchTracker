"""Pipeline JSON API. Routes only read the request, call logic/repository, and return JSON."""

from datetime import date, datetime

from flask import Blueprint, current_app, jsonify, request

from db import get_db
from pipeline import logic
from pipeline import repository as repo

bp = Blueprint("pipeline", __name__, url_prefix="/applications")


def _json_ready(row):
    """Dates as 'YYYY-MM-DD' strings; jsonify would otherwise send an HTTP date format."""
    return {key: value.isoformat() if isinstance(value, (date, datetime)) else value
            for key, value in row.items()}


def _as_form(body):
    """logic.parse_application_form expects form-like strings: turn numbers and null into text."""
    return {key: "" if value is None else str(value) for key, value in body.items()}


def _add_stage_age(application, today):
    """Attach days_in_stage and stale to one application dict."""
    threshold = current_app.config["STALE_DAYS"]
    entered_on = application["stage_entered_on"]
    application["days_in_stage"] = logic.days_in_stage(entered_on, today)
    application["stale"] = logic.is_stale(application["status"], entered_on, today, threshold)


@bp.get("")
def list_applications():
    today = date.today()
    applications = repo.list_applications(get_db())
    for application in applications:
        _add_stage_age(application, today)
    return jsonify(applications=[_json_ready(a) for a in applications],
                   stale_days=current_app.config["STALE_DAYS"])


@bp.post("")
def create():
    data, errors = logic.parse_application_form(_as_form(request.get_json(silent=True) or {}))
    if errors:
        return jsonify(errors=errors), 400
    app_id = repo.create_application(get_db(), data)
    return jsonify(id=app_id), 201


@bp.get("/conversion-rates")
def conversion_rates():
    histories = repo.get_stage_histories_with_source(get_db())
    return jsonify(rates=logic.conversion_rates_by_source(histories))


@bp.get("/active-ids")
def active_ids():
    """Called by the skills service for the gap ranking (the seam, ADR-2 and ADR-6)."""
    return jsonify(ids=sorted(repo.get_active_application_ids(get_db())))


@bp.get("/<int:app_id>")
def detail(app_id):
    """Used by the UI detail page, and by the skills service to check an application exists."""
    conn = get_db()
    application = repo.get_application(conn, app_id)
    if application is None:
        return jsonify(error="Application not found"), 404
    _add_stage_age(application, date.today())
    return jsonify(
        application=_json_ready(application),
        history=[_json_ready(h) for h in repo.get_stage_history(conn, app_id)],
        next_stages=logic.allowed_next_stages(application["current_stage"]),
        stage_order=logic.STAGE_ORDER,
    )


@bp.post("/<int:app_id>/stage")
def change_stage(app_id):
    body = request.get_json(silent=True) or {}
    try:
        repo.change_stage(get_db(), app_id, body.get("stage", ""))
    except LookupError:
        return jsonify(error="Application not found"), 404
    except logic.InvalidTransition as error:
        return jsonify(error=str(error)), 400
    return jsonify(ok=True)
