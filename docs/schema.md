# Schema

- `Concept`: `concept_id`, `prerequisites`, `description`.
- `Activity`: `activity_id`, `type` (`LESSON`, `EXERCISE`), `target_concept`, `duration`, `difficulty` (optional for exercises, `None` for lessons).
- `Event`: `day`, `kind` (`COMPLETED`, `MISSED`, `FAILED_ASSESSMENT`, `DEADLINE_CHANGED`, `BUDGET_CHANGED`), `activity_id`, `minutes_elapsed`, `correct`, `attempt_id`, `value` (new deadline day for `DEADLINE_CHANGED`, new daily budget for `BUDGET_CHANGED`; membership in `EngineConfig.allowed_budgets` is checked by `Engine.record`).
- `PlanContext`: `goal`, `deadline_day`, `budget`, `current_day`.
- `PlanDay`: `day`, `activities` (tuple of activity IDs; `activity_ids` is a read-only alias), `duration` (minutes).
- `PlanContext` (W7): `goal`, `deadline_day`, `budget`, `current_day`, `minutes_used_today` (0 ≤ value ≤ budget; minutes already spent on `current_day`).
- `Plan` (W7): `status`, `days`, `reason`, `shortfall_days`, `options`, `trace`, `best_effort_days` (only with a non-FEASIBLE status, D42).
- `LearnerConcept` (W7): adds `correct_streak` (consecutive correct responses, T5.4); `n_reviews` counts responses on an already evidence-mastered concept (T2.6).
- `Plan`: `status` (`FEASIBLE`, `INFEASIBLE`, `UNKNOWN`), `days`, `shortfall_days`, `options`, `trace`, `reason`.

**Note:** The durations and difficulties in `activities_*.json` are synthetic placeholders for verification.
