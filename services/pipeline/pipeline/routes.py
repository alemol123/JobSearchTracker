"""Pipeline pages. Routes only read the form, call logic/repository, and redirect."""

from datetime import date

from flask import (Blueprint, abort, current_app, flash, redirect, render_template,
                   request, url_for)

from db import get_db
from pipeline import logic
from pipeline import repository as repo

bp = Blueprint("pipeline", __name__, url_prefix="/applications")


def _add_stage_age(application, today):
    """Attach days_in_stage and stale to one application dict for the templates."""
    threshold = current_app.config["STALE_DAYS"]
    entered_on = application["stage_entered_on"]
    application["days_in_stage"] = logic.days_in_stage(entered_on, today)
    application["stale"] = logic.is_stale(application["status"], entered_on, today, threshold)


@bp.get("/")
def list_view():
    conn = get_db()
    today = date.today()
    applications = repo.list_applications(conn)
    for application in applications:
        _add_stage_age(application, today)
    rates = logic.conversion_rates_by_source(repo.get_stage_histories_with_source(conn))
    return render_template("pipeline/list.html", applications=applications, rates=rates,
                           stale_days=current_app.config["STALE_DAYS"])


@bp.route("/new", methods=["GET", "POST"])
def new():
    if request.method == "POST":
        data, errors = logic.parse_application_form(request.form)
        if not errors:
            app_id = repo.create_application(get_db(), data)
            flash("Application added.")
            return redirect(url_for("pipeline.detail", app_id=app_id))
        # Show the form again with what was typed, plus the errors.
        return render_template("pipeline/new.html", form=request.form, errors=errors,
                               sources=logic.SOURCES), 400

    blank = {"date_applied": date.today().isoformat()}
    return render_template("pipeline/new.html", form=blank, errors=[], sources=logic.SOURCES)


@bp.get("/<int:app_id>")
def detail(app_id):
    conn = get_db()
    application = repo.get_application(conn, app_id)
    if application is None:
        abort(404)
    _add_stage_age(application, date.today())
    return render_template("pipeline/detail.html", application=application,
                           history=repo.get_stage_history(conn, app_id),
                           next_stages=logic.allowed_next_stages(application["current_stage"]),
                           stage_order=logic.STAGE_ORDER)


@bp.post("/<int:app_id>/stage")
def change_stage(app_id):
    try:
        repo.change_stage(get_db(), app_id, request.form.get("stage", ""))
        flash("Stage updated.")
    except LookupError:
        abort(404)
    except logic.InvalidTransition as error:
        flash(str(error), "error")
    return redirect(url_for("pipeline.detail", app_id=app_id))
