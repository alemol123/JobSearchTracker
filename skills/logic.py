"""Skill gap rules. Pure functions: no Flask, no SQL, and no knowledge of the
applications table. The caller passes in which application IDs are active
(see ADR-2), so this module works the same after a service split.

tags:       list of (application_id, skill_id) pairs from application_skills
my_skills:  {skill_id: proficiency_level 1-5}
active_ids: set of application IDs whose status is 'active'
"""


def demand_counts(tags, active_ids):
    """{skill_id: number of active applications that require it}."""
    apps_per_skill = {}
    for application_id, skill_id in tags:
        if application_id in active_ids:
            apps_per_skill.setdefault(skill_id, set()).add(application_id)
    return {skill_id: len(apps) for skill_id, apps in apps_per_skill.items()}


def missing_skills(tags, my_skills, active_ids):
    """Skills required by at least one active application that I don't have at all."""
    return set(demand_counts(tags, active_ids)) - set(my_skills)


def rank_by_demand(tags, my_skills, active_ids):
    """Missing skills, most-demanded first; ties broken by skill_id so the order is stable."""
    counts = demand_counts(tags, active_ids)
    ranking = [
        {"skill_id": skill_id, "demand": counts[skill_id]}
        for skill_id in missing_skills(tags, my_skills, active_ids)
    ]
    ranking.sort(key=lambda r: (-r["demand"], r["skill_id"]))
    return ranking
