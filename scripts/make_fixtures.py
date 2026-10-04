import json
import os

CURRICULUM_CONCEPTS = [
    {"concept_id": "C1", "description": "Basic Data Types", "prerequisites": []},
    {"concept_id": "C2", "description": "For & While Loops", "prerequisites": []},
    {"concept_id": "C3", "description": "Lists & Arrays", "prerequisites": ["C1", "C2"]},
    {"concept_id": "C4", "description": "List Comprehensions", "prerequisites": ["C3"]},
]


def make_activities():
    activities = []
    lesson_durations = {"C1": 4, "C2": 4, "C3": 5, "C4": 5}
    exercise_durations = {0.2: 1, 0.4: 1, 0.6: 2, 0.8: 2}

    for c in ["C1", "C2", "C3", "C4"]:
        activities.append(
            {
                "activity_id": f"L-{c}",
                "type": "LESSON",
                "target_concept": c,
                "duration": lesson_durations[c],
                "text": "",
                "_note": "durations are synthetic placeholders",
            }
        )
        for diff in [0.2, 0.4, 0.6, 0.8]:
            activities.append(
                {
                    "activity_id": f"E-{c}-{diff}",
                    "type": "EXERCISE",
                    "target_concept": c,
                    "duration": exercise_durations[diff],
                    "difficulty": diff,
                    "text": "",
                    "_note": "durations are synthetic placeholders",
                }
            )
    return activities


def main():
    os.makedirs("data/curriculum", exist_ok=True)

    with open("data/curriculum/curriculum_4node.json", "w", encoding="utf-8") as f:
        json.dump({"schema_version": 1, "concepts": CURRICULUM_CONCEPTS}, f, indent=2)
        f.write("\n")

    with open("data/curriculum/activities_4node.json", "w", encoding="utf-8") as f:
        json.dump({"schema_version": 1, "activities": make_activities()}, f, indent=2)
        f.write("\n")

    learner_concepts = {
        c: {
            "mastery": 0.20,
            "uncertainty": 0.7219,
            "assessed": False,
            "last_practice_day": None,
            "n_reviews": 0,
            "half_life_days": None,
        }
        for c in ["C1", "C2", "C3", "C4"]
    }
    with open("data/learner_novice.json", "w", encoding="utf-8") as f:
        json.dump({"schema_version": 1, "concepts": learner_concepts}, f, indent=2)
        f.write("\n")

    generate_invalid_fixtures()
    print("Valid and invalid fixtures created.")


def generate_invalid_fixtures():
    os.makedirs("tests/fixtures/invalid", exist_ok=True)

    # helper
    def write_inv(name, data):
        with open(f"tests/fixtures/invalid/{name}.json", "w", encoding="utf-8") as f:
            if isinstance(data, str):
                f.write(data)
            else:
                json.dump(data, f, indent=2)
                f.write("\n")

    # 1. cycle
    write_inv(
        "cycle",
        {
            "schema_version": 1,
            "concepts": [
                {"concept_id": "C1", "description": "", "prerequisites": ["C2"]},
                {"concept_id": "C2", "description": "", "prerequisites": ["C1"]},
            ],
        },
    )
    # 2. self loop
    write_inv(
        "self_loop",
        {
            "schema_version": 1,
            "concepts": [{"concept_id": "C1", "description": "", "prerequisites": ["C1"]}],
        },
    )
    # 3. unknown prereq
    write_inv(
        "unknown_prereq",
        {
            "schema_version": 1,
            "concepts": [{"concept_id": "C1", "description": "", "prerequisites": ["CX"]}],
        },
    )
    # 4. duplicate concept
    write_inv(
        "duplicate_concept",
        {
            "schema_version": 1,
            "concepts": [
                {"concept_id": "C1", "description": "", "prerequisites": []},
                {"concept_id": "C1", "description": "", "prerequisites": []},
            ],
        },
    )
    # 5. bad schema version
    write_inv("bad_schema_version", {"schema_version": 99, "concepts": []})
    # 6. malformed
    write_inv("malformed", "{ malformed json")

    # 7. duplicate activity
    write_inv(
        "duplicate_activity",
        {
            "schema_version": 1,
            "activities": [
                {"activity_id": "A1", "type": "LESSON", "target_concept": "C1", "duration": 5},
                {"activity_id": "A1", "type": "LESSON", "target_concept": "C1", "duration": 5},
            ],
        },
    )
    # 8. exercise no difficulty
    write_inv(
        "exercise_no_difficulty",
        {
            "schema_version": 1,
            "activities": [
                {"activity_id": "A1", "type": "EXERCISE", "target_concept": "C1", "duration": 5}
            ],
        },
    )
    # 9. difficulty low
    write_inv(
        "difficulty_low",
        {
            "schema_version": 1,
            "activities": [
                {
                    "activity_id": "A1",
                    "type": "EXERCISE",
                    "target_concept": "C1",
                    "duration": 5,
                    "difficulty": 0.01,
                }
            ],
        },
    )
    # 10. difficulty high
    write_inv(
        "difficulty_high",
        {
            "schema_version": 1,
            "activities": [
                {
                    "activity_id": "A1",
                    "type": "EXERCISE",
                    "target_concept": "C1",
                    "duration": 5,
                    "difficulty": 0.96,
                }
            ],
        },
    )
    # 11. lesson with difficulty
    write_inv(
        "lesson_with_difficulty",
        {
            "schema_version": 1,
            "activities": [
                {
                    "activity_id": "A1",
                    "type": "LESSON",
                    "target_concept": "C1",
                    "duration": 5,
                    "difficulty": 0.5,
                }
            ],
        },
    )
    # 12. bad duration
    write_inv(
        "bad_duration",
        {
            "schema_version": 1,
            "activities": [
                {"activity_id": "A1", "type": "LESSON", "target_concept": "C1", "duration": "5"}
            ],
        },
    )
    # 13. unknown target
    write_inv(
        "unknown_target",
        {
            "schema_version": 1,
            "activities": [
                {"activity_id": "A1", "type": "LESSON", "target_concept": "CX", "duration": 5}
            ],
        },
    )


if __name__ == "__main__":
    main()
