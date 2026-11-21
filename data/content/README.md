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
| `content_8node_x10.json` | Every activity in `data/curriculum/activities_8node_x10.json` (8 lessons, 80 exercises): the 40 `content_8node.json` entries verbatim plus 48 new exercises (Plan 1, D81) |

> **`8node_x10` status: human-reviewed by the owner (D93, 2026-11-20).** The 48 new exercises
> were drafted by Claude on 2026-11-20, passed `scripts/check_content.py` (all 42 runnable answers
> verified), and were reviewed item by item by the AI
> (`docs/content_reviews/8node_x10_ai_review.md`; one item fixed). The owner then reviewed all
> three `8node_x10` files; `data/review_manifest.json` records reviewer `vhemanth06` with
> `ai_assisted: true` (unchanged sha256). The files load without `allow_unreviewed`, and the demo
> lists `8node_x10` as reviewed. `content_8node.json` is still pending.

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
- Optional `"verify": "output"` on an exercise: its prompt holds exactly one ```` ```python ````
  block, and what the block prints (or the name of the exception it raises) must equal the
  correct option. `scripts/check_content.py` runs it in a sandbox.

## Checking content

```bash
.venv/bin/python scripts/check_content.py data/content/content_8node_x10.json --spread 3,4,3
```

The checker runs `load_content`, then checks that correct-answer positions are balanced within
each concept (no index used for more than half of a concept's exercises), that no two prompts are
duplicates or near-duplicates (at least 90% similar with the same correct answer), the optional
easy/medium/hard spread per concept, and every `verify: output` item. Snippets run in a separate
`python -I -S` process in an empty temporary directory, with no environment variables, CPU and
memory limits, a 5-second timeout, and an audit hook that blocks file, import, os, process and
network access. It prints one line per problem and exits with status 1 if there are any.

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

The script rewrites the entry. Pass `--ai-assisted` to keep `"ai_assisted": true` on it.

## Review process for AI-drafted content (D88)

1. Draft the content and run `scripts/check_content.py` (it also runs every `verify: output`
   snippet).
2. Review every new item and write the result to `docs/content_reviews/<name>_ai_review.md`; fix or
   replace items that fail.
3. Record each new file honestly as pending (no `--edges-reviewed` for curricula):

   ```bash
   .venv/bin/python scripts/record_review.py <file> --pending --ai-assisted --source "ai-drafted, ai-checked"
   ```

   `--pending` sets `reviewer` to `PENDING_HUMAN_REVIEW`. The loader rejects that reviewer like a
   missing entry (and still rejects `"AI"`), so the files need `allow_unreviewed=True`, and every
   demo view and result file that uses them says "content: AI-checked, human review pending".

### Optional human review (outside the plans)

A named human review unblocks the files (done for `8node_x10` on 2026-11-20, D93). After reading every new exercise and the catalogue:

```bash
.venv/bin/python scripts/record_review.py data/curriculum/curriculum_8node_x10.json \
  --reviewer <your-name> --ai-assisted --source "copy of curriculum_8node.json" --edges-reviewed
.venv/bin/python scripts/record_review.py data/curriculum/activities_8node_x10.json \
  --reviewer <your-name> --ai-assisted --source "ai-drafted, human-reviewed"
.venv/bin/python scripts/record_review.py data/content/content_8node_x10.json \
  --reviewer <your-name> --ai-assisted --source "ai-drafted, human-reviewed"
```

No test needs editing: `tests/unit/curriculum/test_loader_review_gate.py` reads the pending set from the manifest
(a reviewed file joins the CI scan), and `tests/unit/curriculum/test_curriculum_x10.py` expects the files to load
once the entry names a reviewer.
