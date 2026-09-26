# Traceability Matrix

This document maps the project milestones (M1–M8) to the acceptance tests (TC-01..12).

| TC-ID | Milestone | Scenario / Input | Expected Result |
|---|---|---|---|
| TC-01 | M3 | Schedule a plan on a graph with an unmet mandatory prerequisite. | No lesson for the locked concept is ever scheduled before its prerequisite. |
| TC-02 | M3 | Generate a plan under a fixed daily budget. | No day's total scheduled duration exceeds the configured budget. |
| TC-03 | M3 | Same learner, same goal, budgets = 5 min vs. 30 min. | The two plans are materially different (different pacing/day count). |
| TC-04 | M2/M3 | Two learners with different prior mastery, same goal/budget. | They receive different, individually valid plans. |
| TC-05 | M5/M7 | A concept is already mastered above threshold. | It is omitted from new-learning scheduling, with a decision trace citing the mastery evidence. |
| TC-06 | M4 | A learner fails an exercise on a low-mastery concept. | Mastery estimate updates downward and a remediation/difficulty response is triggered. |
| TC-07 | M6 | Learner misses a scheduled day. | Replanning produces a new valid plan; no completed work is lost or duplicated. |
| TC-08 | M3 | Goal cannot fit before the deadline given the budget. | Engine returns an infeasibility report with shortfall and corrective options, not an invalid plan. |
| TC-09 | M5 | A high-review-urgency concept and spare daily capacity exist. | The concept receives review priority over lower-urgency new content. |
| TC-10 | M7 | Any generated plan (selected and omitted activities). | Every activity's decision can be traced to state, constraints and score components. |
| TC-11 | M1 | Load the prerequisite graph. | Graph is confirmed acyclic; cycle injection is rejected at load time. |
| TC-12 | M1 | Load curriculum/learner-state schema fixtures. | All required fields are present and typed correctly. |
