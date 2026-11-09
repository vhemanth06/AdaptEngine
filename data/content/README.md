# Learner-facing content

> **Status: AI-drafted, pending human review.** `content_8node.json` was drafted by an AI
> assistant as demo content. Its entry in `data/review_manifest.json` has
> `"reviewer": "PENDING_HUMAN_REVIEW"`. A named human must review it and re-record the entry
> before it is treated as reviewed content.

Content is display-only. The engine (planner, mastery, eligibility) never reads it. The
demo frontend shows it to the learner. The `text` fields in `data/curriculum/activities_*.json`
stay empty.

## Files

| File | Covers |
|---|---|
| `content_8node.json` | Every activity in `data/curriculum/activities_8node.json` (8 lessons, 32 exercises) |

## Schema (`schema_version: 1`)

```json
{
  "schema_version": 1,
  "curriculum": "data/curriculum/curriculum_8node.json",
  "activities_file": "data/curriculum/activities_8node.json",
  "activities": {
    "L-C1": {
      "type": "LESSON",
      "target_concept": "C1",
      "title": "Basic Data Types",
      "markdown": "Lesson body in Markdown, with one small code example."
    },
    "E-C1-0.2": {
      "type": "EXERCISE",
      "target_concept": "C1",
      "prompt": "Markdown question; may contain a fenced code block.",
      "options": ["`float`", "`int`", "`str`", "`bool`"],
      "correct": 0,
      "explanation": "One or two sentences on why the answer is correct."
    }
  }
}
```

- `activities` is keyed by `activity_id`. It must hold exactly the activity ids of the catalogue.
- `type` and `target_concept` must match the activity catalogue.
- LESSON entries need a non-empty `markdown`. `title` is optional display text.
- EXERCISE entries need a non-empty `prompt`, exactly 4 non-empty unique `options`, `correct`
  as an int index 0-3, and a non-empty `explanation`.
- Exercise hardness follows the activity's `difficulty`, which is not repeated here.

## Loading

```python
from adaptengine.curriculum.loader import load_curriculum, load_activities
from adaptengine.curriculum.content import load_content

concepts = load_curriculum("data/curriculum/curriculum_8node.json")
activities = load_activities("data/curriculum/activities_8node.json", concepts)
content = load_content("data/content/content_8node.json", activities)
```

`load_content` raises `adaptengine.core.errors.ValidationError` on any schema problem. It
does not apply the review-manifest gate.

## Re-recording the review

After you edit or review the file, record it with your name:

```bash
.venv/bin/python scripts/record_review.py data/content/content_8node.json \
  --reviewer <your-name> --source "ai-drafted, human-reviewed"
```

The script rewrites the entry and drops the `ai_assisted` flag, so add
`"ai_assisted": true` back by hand.
