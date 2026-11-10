# Final presentation (8–10 minutes) — outline

Numbers from `docs/FINAL_RESULTS.md`; demo steps from `frontend/README.md`.

| Min | Slide / demo | Message | Evidence |
|---|---|---|---|
| 0:00–0:45 | Problem | Goal + deadline + minutes/day → a safe, adaptive, explainable daily plan | — |
| 0:45–1:30 | Architecture | Deterministic core; agents above it propose, the engine decides; everything behind flags | `docs/AGENTS.md` diagram/table |
| 1:30–2:15 | What Week 7 missed | Premature mastery (39–51% false), idle time (≈ 55 of 120 min used), a weak baseline | `w8_probe_baseline.json` |
| 2:15–3:00 | Final changes | Calibrated profile (pre-registered), consolidation, verification probe, horizon-aware strictness | D48–D51 |
| 3:00–7:00 | **Live demo** (steps 1–7 of the script) | Feasibility → diagnostic (optional) → Why? → wrong answers & replan → missed day → Autopilot belief vs reality → Policy Lab fallback | `make demo` |
| 7:00–8:15 | Results | 0 prerequisite violations in all 208 cells; headline 0.939 vs 0.705 (static_loop) and 0.368 (W7); depends on horizon: worse at 7 days, better at 21 | forest plot, KM figure |
| 8:15–9:00 | What did not work | Diagnostic adds nothing; bandit = deterministic; Elo/HLR/forgets worse; S4-fitted calibration mismatch | notes §12 |
| 9:00–9:45 | Limitations & close | Simulated learners only; agents not run with a model; next: pilot, Junyi data, faster scheduler | notes §14 |

Backup slides: pre-registration and amendment; policy spec (D53) and OPE table; authoring review gate; reliability diagrams.
