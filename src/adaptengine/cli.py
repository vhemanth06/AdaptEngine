import sys
import json
import argparse
from .api import Engine
from .session import load_learner, save_learner, load_log, save_log, save_snapshot
from .core.errors import AdaptEngineError
from .core.schema import Event, EventType, PlanContext


def main(argv=None):
    if argv is None:
        argv = sys.argv[1:]

    parser = argparse.ArgumentParser(prog="adaptengine")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # validate
    val_parser = subparsers.add_parser("validate")
    val_parser.add_argument("--curriculum", required=True)
    val_parser.add_argument("--activities", required=True)
    val_parser.add_argument("--manifest")
    val_parser.add_argument("--allow-unreviewed", action="store_true")

    # show
    show_parser = subparsers.add_parser("show")
    show_parser.add_argument("--curriculum", required=True)
    show_parser.add_argument("--activities", default="data/curriculum/activities_4node.json")
    show_parser.add_argument("--manifest")
    show_parser.add_argument("--allow-unreviewed", action="store_true")

    # init-learner
    init_parser = subparsers.add_parser("init-learner")
    init_parser.add_argument("--curriculum", required=True)
    init_parser.add_argument("--activities", default="data/curriculum/activities_4node.json")
    init_parser.add_argument("--out", required=True)
    init_parser.add_argument("--manifest")
    init_parser.add_argument("--allow-unreviewed", action="store_true")

    # update
    upd_parser = subparsers.add_parser("update")
    upd_parser.add_argument("--curriculum", required=True)
    upd_parser.add_argument("--activities", required=True)
    upd_parser.add_argument("--learner", required=True)
    upd_parser.add_argument("--log", required=True)
    upd_parser.add_argument("--activity", required=True)
    upd_parser.add_argument("--response", choices=["correct", "incorrect"])
    upd_parser.add_argument("--day", type=int, required=True)
    upd_parser.add_argument("--attempt-id")
    upd_parser.add_argument("--manifest")
    upd_parser.add_argument("--allow-unreviewed", action="store_true")
    upd_parser.add_argument("--save", action="store_true")
    upd_parser.add_argument("--snapshot")

    # plan
    plan_parser = subparsers.add_parser("plan")
    plan_parser.add_argument("--curriculum", required=True)
    plan_parser.add_argument("--activities", required=True)
    plan_parser.add_argument("--learner", required=True)
    plan_parser.add_argument("--log")
    plan_parser.add_argument("--goal", required=True)
    plan_parser.add_argument("--deadline", type=int, required=True)
    plan_parser.add_argument("--budget", type=int, required=True)
    plan_parser.add_argument("--current-day", type=int, default=1)
    plan_parser.add_argument("--manifest")
    plan_parser.add_argument("--allow-unreviewed", action="store_true")
    plan_parser.add_argument("--json", action="store_true")

    args = parser.parse_args(argv)

    if args.allow_unreviewed:
        print("WARNING: authoring-only mode: allowing unreviewed content", file=sys.stderr)

    try:
        if args.command == "validate":
            engine = Engine.from_files(
                args.curriculum,
                args.activities,
                manifest_path=args.manifest,
                allow_unreviewed=args.allow_unreviewed,
            )
            print(
                f"OK: {len(engine.graph.concepts())} concepts, {len(engine.activities)} activities (reviewed)"
            )

        elif args.command == "show":
            engine = Engine.from_files(
                args.curriculum,
                args.activities,
                manifest_path=args.manifest,
                allow_unreviewed=args.allow_unreviewed,
            )
            print("Concepts:", engine.graph.concepts())
            print(
                "Prerequisites:",
                {c: engine.graph.prerequisites(c) for c in engine.graph.concepts()},
            )
            print("Roots:", engine.graph.roots())
            print("Topological Order:", engine.graph.topological_order())

        elif args.command == "init-learner":
            engine = Engine.from_files(
                args.curriculum,
                args.activities,
                manifest_path=args.manifest,
                allow_unreviewed=args.allow_unreviewed,
            )
            state = engine.init_learner()
            save_learner(state, args.out)
            print(f"Created learner file {args.out}")

        elif args.command == "update":
            engine = Engine.from_files(
                args.curriculum,
                args.activities,
                manifest_path=args.manifest,
                allow_unreviewed=args.allow_unreviewed,
            )
            state = load_learner(args.learner, engine.graph.concepts())
            log = load_log(args.log)

            activity = engine.activities.get(args.activity)
            if not activity:
                raise AdaptEngineError(f"Unknown activity {args.activity}")

            correct = None
            if args.response == "correct":
                correct = True
            elif args.response == "incorrect":
                correct = False

            event = Event(
                day=args.day,
                kind=EventType.COMPLETED,
                activity_id=args.activity,
                minutes_elapsed=activity.duration,
                correct=correct,
                attempt_id=args.attempt_id,
            )
            target = activity.target_concept
            p_before = state.concepts[target].mastery
            h_before = state.concepts[target].uncertainty

            new_state, new_log = engine.record(state, log, event)

            p_after = new_state.concepts[target].mastery
            h_after = new_state.concepts[target].uncertainty
            print(f"{target}: p {p_before:.4f} -> {p_after:.4f}, H {h_before:.4f} -> {h_after:.4f}")

            if args.save:
                save_learner(new_state, args.learner)
                save_log(new_log, args.log)
            if args.snapshot:
                save_snapshot(new_state, new_log, args.snapshot)

        elif args.command == "plan":
            engine = Engine.from_files(
                args.curriculum,
                args.activities,
                manifest_path=args.manifest,
                allow_unreviewed=args.allow_unreviewed,
            )
            state = load_learner(args.learner, engine.graph.concepts())
            done_ids = ()
            if args.log:
                try:
                    log = load_log(args.log)
                    done_ids = log.completed_ids()
                except Exception:
                    done_ids = ()

            ctx = PlanContext(
                goal=args.goal,
                deadline_day=args.deadline,
                budget=args.budget,
                current_day=args.current_day,
            )
            plan_res = engine.plan(state, ctx, done_ids=done_ids)

            if args.json:
                data = {
                    "status": plan_res.status.value,
                    "reason": plan_res.reason,
                    "shortfall_days": plan_res.shortfall_days,
                    "options": list(plan_res.options),
                    "days": [
                        {
                            "day": d.day,
                            "activities": list(d.activities),
                            "duration": d.duration,
                        }
                        for d in plan_res.days
                    ],
                    "trace": list(plan_res.trace),
                }
                print(json.dumps(data, indent=2))
            else:
                print(f"Status: {plan_res.status.value}")
                if plan_res.reason:
                    print(f"Reason: {plan_res.reason}")
                if plan_res.days:
                    print(f"Schedule ({len(plan_res.days)} days):")
                    for d in plan_res.days:
                        print(f"  Day {d.day} ({d.duration} min):")
                        for aid in d.activities:
                            act = engine.activities.get(aid)
                            dur = act.duration if act else "?"
                            print(f"    - {aid} ({dur} min)")
                if plan_res.shortfall_days > 0:
                    print(f"Shortfall: {plan_res.shortfall_days} days")
                if plan_res.options:
                    print("Options:")
                    for opt in plan_res.options:
                        print(f"  - {opt}")

    except AdaptEngineError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
