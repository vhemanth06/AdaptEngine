# Schema

- `Concept`: `concept_id`, `prerequisites`, `description`.
- `Activity`: `activity_id`, `type` (`LESSON`, `EXERCISE`), `target_concept`, `duration`, `difficulty` (optional for exercises, `None` for lessons).
- `Event`: `day`, `kind` (`COMPLETED`, `MISSED`, `FAILED_ASSESSMENT`, `DEADLINE_CHANGED`, `BUDGET_CHANGED`), `activity_id`, `minutes_elapsed`, `correct`, `attempt_id`.
- `PlanContext`: `goal`, `deadline_day`, `budget`, `current_day`.
- `PlanDay`: `day`, `activity_ids`, `minutes_used`.
- `Plan`: `status` (`FEASIBLE`, `INFEASIBLE`, `UNKNOWN`), `days`, `shortfall_days`, `options`, `trace`, `reason`.

**Note:** The durations and difficulties in `activities_*.json` are synthetic placeholders for verification.
