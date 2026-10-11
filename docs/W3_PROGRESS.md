# AdaptEngine — Week 3 (W3) Progress Log

| Workstream | Owner/agent | Status (todo/doing/blocked/done) | Branch | Evidence (tests / run path) | Notes |
|---|---|---|---|---|---|
| Phase 0 Audit | AI Pair Programmer | done | main | `records/W3_AUDIT.md`, `tests/test_defects_repro.py` | 100% defects D-A..D-H reproduced with failing tests. Baseline 47 tests pass. |
| WS1 Strict Validation | AI Pair Programmer | done | main | `tests/test_schema.py`, `tests/test_defects_repro.py` | D-B, D-C, D-E resolved. Validated bounds, types, and config hash. |
| WS2 Review Gate | AI Pair Programmer | done | main | `tests/test_loader_review_gate.py` | D-A, D-F, D-I resolved. Default-on review gate, literal edges_reviewed, named human reviewer. |
| WS3 Persistence | AI Pair Programmer | done | main | `tests/test_state_session.py` | D-G resolved. Atomic snapshot write via .tmp + fsync + os.replace, failure injection tested. |
| WS4 Evidence State | AI Pair Programmer | done | main | `tests/test_mastery.py`, `tests/test_state_session.py` | D-D resolved. Exposure vs evidence separated, attempt idempotency, monotone last_practice_day. |
| WS5 pyBKT Adapter | AI Pair Programmer | done | main | `tests/test_adapter.py` | D6 resolved. MasteryModel protocol, CustomBKT oracle, PyBKTAdapter with parity tests (1e-9). |
| WS6 Diagnostic M2 | AI Pair Programmer | done | main | `tests/test_diagnostic.py` | TC2.1, TC2.2 pass. EIG item selection, cold start UNASSESSED, caps & entropy stopping, descendant skipping. |
| WS7 Docs & Records | AI Pair Programmer | done | main | `docs/*`, `records/*` | Full Appendix A transcribed into docs, 23-ID traceability register, decisions synchronized. |
| WS8 Run Command | AI Pair Programmer | done | main | `scripts/run_w3.py`, `Makefile`, `runs/w3/` | `make w3` passes all 5 gates and writes full auditable evidence directory. |

## Open Decisions Needing Human Input (Section 4) - Defaults Applied

The following decisions are **OPEN – default applied** as instructed in Section 4:
- **D1: Global diagnostic item cap $N_{\max}$** -> Default applied: **8 items**
- **D2: Per-concept item cap** -> Default applied: **3 items**
- **D3: Entropy stop threshold** -> Default applied: **$H(p) \le 0.50$** ($p \le 0.11$ or $p \ge 0.89$)
- **D4: Responses $k$ for evidence-mastered** -> Default applied: **$k = 2$ observed responses and $p \ge \theta$**
- **D5: Value stored after an exercise update** -> Default applied: **post-transition $p''$**; tests assert both $p'$ and $p''$
- **D6: pyBKT mapping of continuous $d$** -> Default applied: **3 item classes**: easy ($d < 0.35$), medium ($0.35 \le d < 0.65$), hard ($d \ge 0.65$)
- **D7: Do lessons raise $p$?** -> Default applied: **Yes, via $T_{\text{lesson}} = 0.20$ as a prior shift; lessons never set assessed or count as evidence**
- **D8: Skip descendants in diagnostic** -> Default applied: **descendants not probed if ancestor ends with $p < 0.40$**
- **D9: Reviewer identity in manifest** -> Default applied: **Human sign-off left to owner; live loading requires named non-"AI" reviewer; `ai_assisted: true` added**
- **D10: Tie-break** -> Default applied: **smaller $|d - 0.5|$, then lexicographic `activity_id`**

---

## Log Entries

### 2026-10-11 — Phase 0: Audit Completed
- Configured local environment with uv and Python.
- Verified test baseline: 47 passed, 92% statement coverage, clean ruff check & format.
- Created `tests/test_defects_repro.py` reproducing defects D-A through D-H.
- Generated `records/W3_AUDIT.md`.

### 2026-10-11 — WS1 Strict Validation Completed
- Implemented `adaptengine.core.validators` with strict boolean, probability, range, and enum checks.
- Enhanced `adaptengine.core.config` with runtime bounds validation and SHA-256 serialization hashing.
- Updated curriculum loader and graph to type-check collections and reject unknown prerequisites before edge creation (`unknown_prereq.json` raises `UnknownConceptError`).
- Bounded learning transition $T \in [0, 1]$ in mastery update.

### 2026-10-11 — WS2 Review Gate Completed
- Made curriculum review validation enabled by default at all entry points (CLI and API).
- Standardized manifest key path resolution relative to content root and manifest directory.
- Hardened review gate to require named human reviewer (rejecting `"AI"` or empty) and strict boolean `edges_reviewed is True`.
- Added caller-configurable `--curriculum` and `--activities` paths in CLI commands.

### 2026-10-11 — WS3 Persistence Completed
- Implemented atomic file writing in `adaptengine.session` (`.tmp` write, flush, fsync, atomic `os.replace`).
- Added unified snapshot format saving learner state and event log simultaneously.
- Verified with failure-injection tests proving corrupted writes never destroy active state files.

### 2026-10-11 — WS4 Evidence-State Semantics Completed
- Separated lesson exposure from exercise assessment evidence in `LearnerConcept`.
- Added `lessons_done`, `responses`, `correct_responses`, `status` (`UNASSESSED`/`ASSESSED`), and `seen_attempt_ids`.
- Implemented attempt idempotency (duplicate attempts are ignored no-ops).
- Enforced monotonic `last_practice_day = max(old, day)`.

### 2026-10-11 — WS5 pyBKT Adapter Completed
- Defined `MasteryModel` protocol, `CustomBKT` oracle, and `PyBKTAdapter` in `adaptengine.learner.adapter`.
- Mapped continuous difficulty to 3 discrete item classes (easy, medium, hard) matching `CustomBKT` within $10^{-9}$ at representative difficulties.
- Verified pyBKT isolation (pyBKT imported only in adapter).

### 2026-10-11 — WS6 Diagnostic M2 Completed
- Created `adaptengine.diagnostic` with Expected Information Gain (EIG) item selection.
- Enforced D1 global cap ($N_{\max} \le 8$), D2 concept cap (3), D3 entropy stopping ($H \le 0.50$), and D8 ancestor unmastered descendant skipping ($p < 0.40$).
- Ensured cold start concepts remain `UNASSESSED` and existing learner state is preserved. Passed TC2.1 and TC2.2.

### 2026-10-11 — WS7 Documentation and Records Completed
- Transcribed finalized design (Appendix A) into:
  - `docs/ARCHITECTURE.md`
  - `docs/MASTERY_MODEL.md`
  - `docs/DIAGNOSTIC.md`
  - `docs/IMPLEMENTATION_PLAN.md`
  - `docs/EVALUATION_PROTOCOL.md`
  - `docs/TECHNICAL_FEASIBILITY.md`
  - `docs/reuse_inventory.md`
  - `docs/README.md`
- Synchronized `README.md`, `records/TRACEABILITY.md` (23-ID register), `records/DECISIONS.md`, and `records/AI_USE.md`.

### 2026-10-11 — WS8 Run Command and Quality Gates Completed
- Implemented `scripts/run_w3.py` executing all 5 gates and writing auditable evidence under `runs/w3/<run-id>/`.
- Added Makefile target `make w3` with virtualenv auto-detection.
- Executed `make w3`: All 5 gates passed (Ruff clean, 80 tests passing, reference constants verified, architecture layering clean, scripted persona demo verified).

