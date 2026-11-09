# Data Manifest

## Current Datasets
- 4-Node Synthetic Curriculum (`data/curriculum/curriculum_4node.json`)
- 4-Node Synthetic Activities (`data/curriculum/activities_4node.json`)
- 8-Node Synthetic Curriculum (`data/curriculum/curriculum_8node.json`)
- 8-Node Synthetic Activities (`data/curriculum/activities_8node.json`)
- Novice Learner Profile (`data/learner_novice.json`)

## External learner data (WP7)

Raw files live in `data/external/` and are not committed. Rebuild and verify them with
`python scripts/download_data.py` (`--verify-only` needs no network). SHA-256 values are in
`data/external/CHECKSUMS` (`sha256sum` format). Access date for all sources: **8 Nov 2026**.

Both datasets are **maths**, not Python programming. Fitted parameters give realistic ranges and
shapes for the simulator and a calibration benchmark for the fitting code. They are not parameter
values for AdaptEngine's learners.

| File | Rows | SHA-256 |
|---|---|---|
| `as.csv` | 525,534 | `f22e3fb7872c1784ce93b0f9ebabbe0cbcac4f896fd8b4a11667b9715d77dbdc` |
| `assist09_skill_builder.csv` | 346,860 | `162ef8d2d28bcbfea6591a282994062bd8d5eaa00636544292a0d268dca6e5da` |
| `ct.csv` | 16,857 | `161e598a609ecdf829938f8453c15da445ca0c65558367e95ac9f412929b9e55` |

### ASSISTments 2009–10 skill-builder (`as.csv`, `assist09_skill_builder.csv`)

- **Data page:** https://sites.google.com/site/assistmentsdata/home/2009-2010-assistment-data/skill-builder-data-2009-2010
  (the page asks publications to give this exact URL).
- **Citation the page requests** (the page notes this 2009 paper does not use this data):
  Feng, M., Heffernan, N.T., & Koedinger, K.R. (2009). Addressing the assessment challenge in an
  Intelligent Tutoring System that tutors as it assesses. *The Journal of User Modeling and
  User-Adapted Interaction*, 19, 243–266.
- **The two files hold the same 346,860 answers in two layouts.** Count them as one dataset.
  Both have the same 346,860 `order_id` values, and `user_id` and `correct` agree on 100% of them.
  Read both with `encoding="ISO-8859-15"`.
- `as.csv`: original layout, **one row per (answer, skill)**, so multi-skill problems repeat.
  Source: https://raw.githubusercontent.com/CAHLR/pyBKT-examples/master/data/as.csv (pyBKT's own
  `Model.fetch_dataset` docstring uses this URL). 525,534 rows, 30 columns, 346,860 unique
  `order_id`, 4,217 students, 26,688 problems, 110 skill names, 78,690 rows without `skill_name`.
  pyBKT maps its columns automatically.
- `assist09_skill_builder.csv`: the page's "corrected version" without duplicate records, **one row
  per student-problem**, with multi-skill IDs joined (e.g. `1_13`). It has an extra unnamed index
  column, so read it with `index_col=0`. Manual download from Google Drive:
  https://drive.google.com/file/d/1NNXHFRxcArrU0ZJSb9BIL56vmUt5FhlE/view?usp=sharing.
  346,860 rows, 30 data columns, 4,217 students, 26,688 problems, 101 skill names, 72,270 rows
  without `skill_name`.
- **Use in W7:** `as.csv` → per-skill BKT fits. The collapsed file → item difficulty
  (1 − proportion correct per `problem_id`, problems with ≥ 20 answers).
- **Cleaning used for fits** (`experiments/fit_bkt.py`, `load_assist`; counts are rows):
  525,534 raw → 449,220 with `original == 1` → 421,318 with a `skill_name` → 300,389 after one
  row per (`order_id`, `skill_name`) → **297,016 rows, 81 skills, 4,125 students** after keeping
  skills with ≥ 100 students (correct rate 0.6608).

### Cognitive Tutor sample (`ct.csv`)

- **Source:** https://raw.githubusercontent.com/CAHLR/pyBKT-examples/master/data/ct.csv. The
  pyBKT-examples README says its Cognitive Tutor data comes from the KDD Cup 2010 downloads
  (https://pslcdatashop.web.cmu.edu/KDDCup/downloads.jsp). Which KDD Cup data set it was cut from
  is not stated. Timestamps run from 2006-09-07 to 2007-06-08, so it is a 2006–07 school-year
  subset. This is not verified.
- **Citation the KDD Cup page requests:** Stamper, J., Niculescu-Mizil, A., Ritter, S., Gordon,
  G.J., & Koedinger, K.R. (2010). [Data set name]. [Challenge/Development] data set from KDD Cup
  2010 Educational Data Mining Challenge. Find it at
  http://pslcdatashop.web.cmu.edu/KDDCup/downloads.jsp
- **Layout:** KDD Cup student-step export, one row per step (first attempt). The 20 columns
  include `Row`, `Anon Student Id`, `Problem Name`, `Step Name`, `Correct First Attempt` and
  `KC(Default)`, plus an unnamed leading index column.
- **Counts:** 16,857 rows, 587 students, 12 KCs, 550 problems, first-attempt correct rate 0.6191.
  It spans four units: RATIO-PROPORTION 11,599 rows, RATIONAL-IRRATIONAL-NUMBERS 4,336,
  LINEAR-SYSTEMS-SOLVING 518 and INEQUALITY-SYSTEMS-SOLVING 404.
- **Use in W7:** the development set for the fitting pipeline (T7.2) and the second-domain check
  (T7.6). The same ≥ 100-students-per-skill rule leaves 9 KCs (15,935 rows, 550 students).

### Deferred

- **CSEDM 2019** (DataShop dataset 2865) is deferred to W8. The download returned a 0-byte file.
  `data/external/csedm2019/` was never created on this machine, so there was nothing to delete.
