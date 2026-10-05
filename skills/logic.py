"""Skill gap rules. Pure functions: no Flask, no SQL, and no knowledge of the
applications table. The caller passes in which application IDs are active
(see ADR-2), so this module works the same after a service split.

tags:       list of (application_id, skill_id) pairs from application_skills
my_skills:  {skill_id: proficiency_level 1-5}
active_ids: set of application IDs whose status is 'active'
"""

MAX_PROFICIENCY = 5


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


def priority_scores(tags, my_skills, active_ids):
    """Which demanded skills to work on first: score = demand x proficiency gap.

    gap = 5 - my proficiency (a skill I don't have counts as 0, so gap 5).
    Skills I'm already at 5 in have nothing to improve and are left out.
    Sorted by score, then demand (both highest first), then skill_id.
    """
    result = []
    for skill_id, demand in demand_counts(tags, active_ids).items():
        proficiency = my_skills.get(skill_id, 0)
        gap = MAX_PROFICIENCY - proficiency
        if gap == 0:
            continue
        result.append({
            "skill_id": skill_id,
            "demand": demand,
            "proficiency": proficiency,
            "gap": gap,
            "score": demand * gap,
        })
    result.sort(key=lambda r: (-r["score"], -r["demand"], r["skill_id"]))
    return result
