from skills.logic import demand_counts, missing_skills, rank_by_demand

# Skill IDs used in these tests
PYTHON, SQL, DOCKER, REACT = 1, 2, 3, 4

# (application_id, skill_id) pairs, like rows of application_skills
TAGS = [
    (10, PYTHON), (10, SQL),            # application 10
    (11, PYTHON), (11, DOCKER),         # application 11
    (12, PYTHON), (12, DOCKER),         # application 12
    (13, REACT),                        # application 13 (rejected in most tests)
]


# ---------- demand_counts ----------

def test_demand_counts_number_of_active_applications_per_skill():
    counts = demand_counts(TAGS, active_ids={10, 11, 12, 13})

    assert counts == {PYTHON: 3, SQL: 1, DOCKER: 2, REACT: 1}


def test_demand_counts_ignore_closed_applications():
    # 13 is rejected/withdrawn, so it is not in active_ids
    counts = demand_counts(TAGS, active_ids={10, 11, 12})

    assert REACT not in counts
    assert counts[PYTHON] == 3


def test_demand_counts_with_no_active_applications():
    assert demand_counts(TAGS, active_ids=set()) == {}


# ---------- missing_skills ----------

def test_missing_skills_are_demanded_skills_i_do_not_have():
    my_skills = {PYTHON: 4}

    assert missing_skills(TAGS, my_skills, active_ids={10, 11, 12}) == {SQL, DOCKER}


def test_skill_only_wanted_by_closed_application_is_not_missing():
    assert REACT not in missing_skills(TAGS, my_skills={}, active_ids={10, 11, 12})


def test_low_proficiency_still_counts_as_having_the_skill():
    # missing = not in my_skills at all; weak skills are handled by the priority score
    assert missing_skills(TAGS, {PYTHON: 1, SQL: 1, DOCKER: 1}, active_ids={10, 11, 12}) == set()


def test_no_tags_means_nothing_is_missing():
    assert missing_skills([], my_skills={}, active_ids={10}) == set()


# ---------- rank_by_demand ----------

def test_missing_skills_ranked_most_demanded_first():
    ranking = rank_by_demand(TAGS, my_skills={}, active_ids={10, 11, 12})

    assert ranking == [
        {"skill_id": PYTHON, "demand": 3},
        {"skill_id": DOCKER, "demand": 2},
        {"skill_id": SQL, "demand": 1},
    ]


def test_ranking_leaves_out_skills_i_already_have():
    ranking = rank_by_demand(TAGS, my_skills={PYTHON: 2}, active_ids={10, 11, 12})

    assert [r["skill_id"] for r in ranking] == [DOCKER, SQL]


def test_ties_are_ordered_by_skill_id_so_the_ranking_is_stable():
    tags = [(1, REACT), (2, SQL)]

    ranking = rank_by_demand(tags, my_skills={}, active_ids={1, 2})

    assert [r["skill_id"] for r in ranking] == [SQL, REACT]


def test_ranking_changes_when_an_application_leaves_the_pipeline():
    before = rank_by_demand(TAGS, my_skills={}, active_ids={10, 11, 12})
    after = rank_by_demand(TAGS, my_skills={}, active_ids={10})  # 11 and 12 rejected

    assert before[0] == {"skill_id": PYTHON, "demand": 3}
    assert {"skill_id": DOCKER, "demand": 2} in before
    assert DOCKER not in [r["skill_id"] for r in after]
