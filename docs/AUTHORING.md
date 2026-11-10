# A0 Authoring Aid — drafting curriculum content with a human review gate (D54)

1. **Draft** (AI-assisted, never live):
   ```bash
   adaptengine author draft --name py_dicts --topic "Python dictionaries" --concepts 6 \
       --provider stub            # or anthropic[:model] / ollama[:model]; --cache DIR to replay
   ```
   Writes `data/drafts/py_dicts/{curriculum,activities,content}_py_dicts.json` and
   `draft_meta.json` (`ai_assisted: true`, `reviewer: "PENDING_HUMAN_REVIEW"`, provider, model,
   prompt hash, timestamp). Loader errors are fed back to the provider (max 2 retries).
2. **Validate:** `adaptengine author validate --name py_dicts` → typed report: schema/DAG errors,
   duplicate or near-duplicate questions, answer-position bias, difficulty spread per concept
   (a hard item is needed for the D50 verification probe), reading length.
3. **Human review:** read every lesson and question; check the prerequisite edges; edit the draft
   files.
4. **Approve (human only):**
   ```bash
   python scripts/record_review.py --promote-draft py_dicts --reviewer "Your Name"
   ```
   Rejects empty, `PENDING…` and AI/model reviewer names; refuses to overwrite live files; copies
   the three files into `data/curriculum/` and `data/content/` and records their SHA-256 in
   `data/review_manifest.json` (`ai_assisted: true`, `edges_reviewed: true`). The engine's loaders
   refuse any file without a matching manifest entry.

The demo's Authoring Studio screen runs the same steps through `/api/authoring/draft`,
`/api/authoring/validate` and `/api/authoring/approve`.
