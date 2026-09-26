# AdaptEngine

**Adaptive Learning, Diagnostic Assessment and Personalized Path-Planning Engine**

**Course:** CS5903 Distributed AI Training, IIT Hyderabad  
**Group:** 15  
**Student:** Vuppula Hemanth Reddy (AI23BTECH11033)

## Overview
AdaptEngine is a backend policy and recommendation engine designed for quantitative disciplines. It continually assesses the learner's estimated mastery and time-bound constraints to construct optimized learning paths, recommend specific activities, and generate transparent, machine-readable justifications for all scheduling decisions.

## Architecture
- **Actors:** Learner and the Engine.
- **Interfaces:** A Python library/API and a thin CLI.

## Setup Instructions
```bash
pip install -r requirements.txt
pip install -r requirements-dev.txt
```

## Quickstart
*(To be added)*

## Limitations
- Excludes full LMS, production UI, neural mastery models.
- Operates on strict assumptions regarding DAGs, indivisible lesson durations, fixed daily time budgets, and binary observability of mastery.