# AI review of the 48 new `8node_x10` exercises (Plan 1.5, P1.5-T2; D88)

- **File:** `data/content/content_8node_x10.json` (new exercises `E-Cn-0.1`, `0.3`, `0.45`, `0.55`,
  `0.7`, `0.9` for C1–C8; the 40 entries copied from `content_8node.json` are not part of this review).
- **Reviewer:** Claude (AI), 2026-11-20. **This is not a human review.** Under D88 the file is recorded
  as `PENDING_HUMAN_REVIEW` in `data/review_manifest.json`; a named human review is optional and
  recorded with `scripts/record_review.py --reviewer <name>`.
- **Method:** each item was read in full (prompt, the four options, correct index, explanation) and
  checked against the columns below. Every `"verify": "output"` item was also run through
  `scripts/check_content.py::run_snippet` (sandboxed subprocess); its printed output, or the name of
  the exception it raises, was compared with the correct option.
- **Result:** 48 items reviewed; 1 fixed (`E-C2-0.1`), 47 pass unchanged; 42 of 42 run
  checks match. After the fix, `python scripts/check_content.py data/content/content_8node_x10.json
  --spread 3,4,3` reports OK.

Columns: **Correct & only** = the stated answer is right and no other option is defensible;
**Distractors** = plausible and clearly wrong; **Scope** = on-concept and uses only the concept and
its prerequisites (no loops in C6 items, no comprehensions in C5 or C8 items); **Difficulty** = the
D6 class fits the item; **Explanation** = correct and matches the answer; **Run check** = sandboxed
run result vs the correct option.

| Item | Class (d) | Correct option | Correct & only | Distractors | Scope | Difficulty | Explanation | Run check | Verdict | Notes |
|---|---|---|---|---|---|---|---|---|---|---|
| `E-C1-0.1` | easy (0.1) | `<class 'str'>` | yes | yes | yes | yes | yes | matches | Pass |  |
| `E-C1-0.3` | easy (0.3) | `2.5` | yes | yes | yes | yes | yes | matches | Pass |  |
| `E-C1-0.45` | medium (0.45) | `12.5` | yes | yes | yes | yes | yes | matches | Pass |  |
| `E-C1-0.55` | medium (0.55) | `7.0` | yes | yes | yes | yes | yes | matches | Pass |  |
| `E-C1-0.7` | hard (0.7) | `-4 1` | yes | yes | yes | yes | yes | matches | Pass |  |
| `E-C1-0.9` | hard (0.9) | `False 26` | yes | yes | yes | yes | yes | matches | Pass | Combines two facts (float rounding, base-16 parsing); fits hard. |
| `E-C2-0.1` | easy (0.1) | `break` | yes (after fix) | yes (after fix) | yes | yes | yes | n/a (concept question) | Fixed | **Fixed.** The distractor `return` also ends a loop when the loop is inside a function, so two options were defensible. Replaced with `end` (not a Python keyword); explanation extended. Correct index unchanged. |
| `E-C2-0.3` | easy (0.3) | `a-b-c-` | yes | yes | yes | yes | yes | matches | Pass | Loops over a string literal. C2 has no prerequisites; a string literal is used the same way in `L-C2` (`print("step", i)`), and the item tests only the loop and `end=`. Kept. |
| `E-C2-0.45` | medium (0.45) | `4` | yes | yes | yes | yes | yes | matches | Pass |  |
| `E-C2-0.55` | medium (0.55) | `12` | yes | yes | yes | yes | yes | matches | Pass |  |
| `E-C2-0.7` | hard (0.7) | `2` | yes | yes | yes | yes | yes | matches | Pass |  |
| `E-C2-0.9` | hard (0.9) | `103` | yes | yes | yes | yes | yes | matches | Pass | `while ... else` with a `break` that never fires; fits hard. |
| `E-C3-0.1` | easy (0.1) | `3` | yes | yes | yes | yes | yes | matches | Pass |  |
| `E-C3-0.3` | easy (0.3) | `c` | yes | yes | yes | yes | yes | matches | Pass |  |
| `E-C3-0.45` | medium (0.45) | `[1, 2, 3]` | yes | yes | yes | yes | yes | matches | Pass | At the easy end of medium; kept (3/4/3 spread). |
| `E-C3-0.55` | medium (0.55) | `6` | yes | yes | yes | yes | yes | matches | Pass |  |
| `E-C3-0.7` | hard (0.7) | `[1, 2, 3] [99, 2, 3]` | yes | yes | yes | yes | yes | matches | Pass |  |
| `E-C3-0.9` | hard (0.9) | `[4, 7]` | yes | yes | yes | yes | yes | matches | Pass | Mutating a list while iterating; fits hard. |
| `E-C4-0.1` | easy (0.1) | `[x ** 2 for x in range(4)]` | yes | yes | yes | yes | yes | n/a (concept question) | Pass |  |
| `E-C4-0.3` | easy (0.3) | `[2, 3, 1]` | yes | yes | yes | yes | yes | matches | Pass |  |
| `E-C4-0.45` | medium (0.45) | `['A', 'C']` | yes | yes | yes | yes | yes | matches | Pass | Uses `str.upper()`, a basic string method (C1 is an ancestor of C4). |
| `E-C4-0.55` | medium (0.55) | `[1, 2, 3, 4]` | yes | yes | yes | yes | yes | matches | Pass |  |
| `E-C4-0.7` | hard (0.7) | `10 [0, 1, 4]` | yes | yes | yes | yes | yes | matches | Pass | Tests that a comprehension variable does not leak; a comprehension fact that does not need C5 (functions and scope). |
| `E-C4-0.9` | hard (0.9) | `[0, 2, 4]` | yes | yes | yes | yes | yes | matches | Pass |  |
| `E-C5-0.1` | easy (0.1) | `None` | yes | yes | yes | yes | yes | n/a (concept question) | Pass |  |
| `E-C5-0.3` | easy (0.3) | `hi world` | yes | yes | yes | yes | yes | matches | Pass |  |
| `E-C5-0.45` | medium (0.45) | `21` | yes | yes | yes | yes | yes | matches | Pass |  |
| `E-C5-0.55` | medium (0.55) | `local` | yes | yes | yes | yes | yes | matches | Pass |  |
| `E-C5-0.7` | hard (0.7) | `UnboundLocalError` | yes | yes | yes | yes | yes | matches | Pass | The answer is the exception name, the convention the checker uses for snippets that raise (other items have `TypeError` options). |
| `E-C5-0.9` | hard (0.9) | `12 12` | yes | yes | yes | yes | yes | matches | Pass | Late binding of a loop variable in closures; fits hard. |
| `E-C6-0.1` | easy (0.1) | `{}` | yes | yes | yes | yes | yes | n/a (concept question) | Pass |  |
| `E-C6-0.3` | easy (0.3) | `2` | yes | yes | yes | yes | yes | matches | Pass |  |
| `E-C6-0.45` | medium (0.45) | `{'x': 5, 'y': 2}` | yes | yes | yes | yes | yes | matches | Pass |  |
| `E-C6-0.55` | medium (0.55) | `{2, 3} {1}` | yes | yes | yes | yes | yes | matches | Pass |  |
| `E-C6-0.7` | hard (0.7) | `2 True` | yes | yes | yes | yes | yes | matches | Pass |  |
| `E-C6-0.9` | hard (0.9) | `{True: 'float'}` | yes | yes | yes | yes | yes | matches | Pass | `True == 1 == 1.0` as dict keys; fits hard. |
| `E-C7-0.1` | easy (0.1) | `__init__` | yes | yes | yes | yes | yes | n/a (concept question) | Pass |  |
| `E-C7-0.3` | easy (0.3) | `7` | yes | yes | yes | yes | yes | matches | Pass |  |
| `E-C7-0.45` | medium (0.45) | `True False` | yes | yes | yes | yes | yes | matches | Pass |  |
| `E-C7-0.55` | medium (0.55) | `21 C` | yes | yes | yes | yes | yes | matches | Pass |  |
| `E-C7-0.7` | hard (0.7) | `0.01 0.01` | yes | yes | yes | yes | yes | matches | Pass |  |
| `E-C7-0.9` | hard (0.9) | `True False` | yes | yes | yes | yes | yes | matches | Pass |  |
| `E-C8-0.1` | easy (0.1) | Calls the parent class's version of `method` | yes | yes | yes | yes | yes | n/a (concept question) | Pass |  |
| `E-C8-0.3` | easy (0.3) | `2 4` | yes | yes | yes | yes | yes | matches | Pass |  |
| `E-C8-0.45` | medium (0.45) | `True False` | yes | yes | yes | yes | yes | matches | Pass |  |
| `E-C8-0.55` | medium (0.55) | `area 9` | yes | yes | yes | yes | yes | matches | Pass |  |
| `E-C8-0.7` | hard (0.7) | `False 5` | yes | yes | yes | yes | yes | matches | Pass |  |
| `E-C8-0.9` | hard (0.9) | `hi HELLO` | yes | yes | yes | yes | yes | matches | Pass | Class attribute changed after the objects exist; fits hard. |
