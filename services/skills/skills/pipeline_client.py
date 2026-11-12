"""The only place the skills service talks to the pipeline service (over HTTP).

Every call has a timeout, and every kind of failure (no answer, timeout, error
status, bad JSON) becomes one exception, PipelineUnavailable, so the routes only
have one thing to handle.
"""

import os

import requests


class PipelineUnavailable(Exception):
    """The pipeline service did not answer in time or answered with an error."""


def _base_url():
    return os.environ.get("PIPELINE_URL", "http://pipeline:8000").rstrip("/")


def _timeout():
    return float(os.environ.get("PIPELINE_TIMEOUT_S", "2"))


def get_active_application_ids():
    """Set of IDs of active applications. Used by GET /skills/gap."""
    try:
        response = requests.get(f"{_base_url()}/applications/active-ids", timeout=_timeout())
        response.raise_for_status()                 # 4xx/5xx -> requests.HTTPError
        return set(response.json()["ids"])
    except (requests.RequestException, ValueError, KeyError) as error:
        raise PipelineUnavailable(str(error)) from error


def application_exists(app_id):
    """True/False from pipeline's answer (200/404). Used before tagging, instead of a foreign key."""
    try:
        response = requests.get(f"{_base_url()}/applications/{app_id}", timeout=_timeout())
    except requests.RequestException as error:
        raise PipelineUnavailable(str(error)) from error
    if response.status_code == 404:
        return False
    if response.status_code != 200:
        raise PipelineUnavailable(f"pipeline answered {response.status_code}")
    return True
