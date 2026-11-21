# Report pipeline (D100)

`results/*.json` → `extract.py` → `data/*.csv` (one per table or figure; every row has
`experiment`, `source_file`, `code_hash`, `status`) → `render_tables.py` → `tables/*.tex` (booktabs)
and `tables/*.md`; `render_figures.py` → `figures/*.pdf` and `figures/*.png` (300 dpi).

- A missing results file gives rows with `status = not_run` and empty values; tables show "not run".
- Render scripts read only `data/`. Re-rendering is byte-identical (fixed file metadata).
- Restyle: edit `style.py`, then `make v2-figures` (seconds). Table columns and captions are in
  `render_tables.py`.

## Section → tables and figures

| Section | Tables | Figures |
|---|---|---|
| 5.1 Out-of-order teaching | T1 executed violations per arm (E1, E4, E5); T1b plan validity (E1, E5); T2 shortfall: CP-SAT exact vs greedy bound-based (E5) | F1 violations per arm, log scale (E1) |
| 5.2 What the learner knows | T3 diagnostic matrix (E2); T4 scripted learners (E2) | F2 Brier vs questions (E2) |
| 5.3 Trustworthy probabilities | T5 real-data held-out metrics (E3 A); T6 fitted − heuristic (E3 B); T6b P(correct) on executed attempts (E1) | F3 reliability, ASSISTments and Cognitive Tutor (E3 A); F3b reliability on executed attempts (E1) |
| 5.4 Does adaptation pay off | T7 headline cells (E1); T8 adapt vs static counts (E1); T9 bisect_confirm − sweep (E4); T10 the 2×2 (E4); T11 replanning under disruptions (E1) | F4 goal mastery vs total minutes (E4); F5 spaced-review retention (E1) |
| 5.5 Which planner | T12 verdict agreement, UNKNOWN rate, shortfall (E5); T12b path feasibility (E5; greedy = E1 adapt); T13 cold-start latency; T13b replan latency (E5) | F6 latency, cold start and replan (E5) |
| 5.6 Sensitivity | T14 real-data world, exploratory (E6) | F7 adapt − static heatmap (E1); F8 θ × k (E6); F9 one-at-a-time scans (E6) |
| All | H: every pre-registered hypothesis, held or failed | — |

## 5.7 Limitations checklist

- The learners are simulated (§V2.3); real students appear only in E3 Part A (maths data, not
  Python), and S4-assist09 borrows their fitted guess/slip.
- `8node_x10` was AI-drafted and reviewed by the owner (D93); synthetic curricula are unreviewed.
- F4 (prerequisite regression handling) and the 16-concept curriculum were not built (D91).
- The report uses the final study only (D98, D101); earlier runs stay in `experiments/`.
- Latency is machine-dependent timing (CPU recorded in `E5_latency.json`).
