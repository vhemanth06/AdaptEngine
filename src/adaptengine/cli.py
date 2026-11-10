import sys
import json
import argparse
from .api import Engine
from .session import (
    load_learner,
    save_learner,
    load_log,
    save_log,
    save_snapshot,
    load_snapshot,
)
from .planner import serialize_plan
from .core.config import DEFAULT_CONFIG
from .core.errors import AdaptEngineError, ValidationError
from .core.schema import Event, EventType, PlanContext, PlanStatus
from .learner.state import ExecutionLog


def _resolve_model(model_name: str | None, cfg=DEFAULT_CONFIG):
    if not model_name or model_name.lower() in ("custom", "custombkt"):
        from .learner.adapter import CustomBKT

        return CustomBKT(cfg)
    elif model_name.lower() in ("pybkt", "pybktadapter"):
        from .learner.adapter import PyBKTAdapter

        return PyBKTAdapter(cfg)
    else:
        raise ValidationError(f"Unknown model '{model_name}'. Allowed: 'custombkt', 'pybkt'")


def main(argv=None):
    if argv is None:
        argv = sys.argv[1:]

    parser = argparse.ArgumentParser(prog="adaptengine")
    subparsers = parser.add_subparsers(dest="command", required=True)
    # T9.1: options shared by every subcommand live on one parent parser
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--allow-unreviewed", action="store_true")

    # validate
    val_parser = subparsers.add_parser("validate", parents=[common])
    val_parser.add_argument("--curriculum", required=True)
    val_parser.add_argument("--activities", required=True)
    val_parser.add_argument("--manifest")

    # show
    show_parser = subparsers.add_parser("show", parents=[common])
    show_parser.add_argument("--curriculum", required=True)
    show_parser.add_argument("--activities", default="data/curriculum/activities_4node.json")
    show_parser.add_argument("--manifest")

    # init-learner
    init_parser = subparsers.add_parser("init-learner", parents=[common])
    init_parser.add_argument("--curriculum", required=True)
    init_parser.add_argument("--activities", default="data/curriculum/activities_4node.json")
    init_parser.add_argument("--out")
    init_parser.add_argument("--snapshot")
    init_parser.add_argument("--goal")
    init_parser.add_argument("--deadline", type=int)
    init_parser.add_argument("--budget", type=int)
    init_parser.add_argument("--manifest")

    # update
    upd_parser = subparsers.add_parser("update", parents=[common])
    upd_parser.add_argument("--curriculum", required=True)
    upd_parser.add_argument("--activities", required=True)
    upd_parser.add_argument("--snapshot")
    upd_parser.add_argument("--learner")
    upd_parser.add_argument("--log")
    upd_parser.add_argument("--activity", required=True)
    upd_parser.add_argument("--response", choices=["correct", "incorrect"])
    upd_parser.add_argument("--day", type=int, required=True)
    upd_parser.add_argument("--attempt-id")
    upd_parser.add_argument("--manifest")
    upd_parser.add_argument("--save", action="store_true")
    upd_parser.add_argument(
        "--model",
        choices=["custombkt", "pybkt"],
        default="custombkt",
        help="Mastery model: 'custombkt' (default) or 'pybkt'",
    )

    # Event recording commands: missed-day
    for name in ("missed-day", "record-missed-day"):
        m_parser = subparsers.add_parser(name, parents=[common])
        m_parser.add_argument("--curriculum", required=True)
        m_parser.add_argument("--activities", required=True)
        m_parser.add_argument("--snapshot", required=True)
        m_parser.add_argument("--day", type=int, required=True)
        m_parser.add_argument("--attempt-id")
        m_parser.add_argument("--manifest")
        m_parser.add_argument(
            "--model",
            choices=["custombkt", "pybkt"],
            default="custombkt",
            help="Mastery model: 'custombkt' (default) or 'pybkt'",
        )

    # Event recording commands: failed-assessment
    for name in ("failed-assessment", "record-failed-assessment"):
        f_parser = subparsers.add_parser(name, parents=[common])
        f_parser.add_argument("--curriculum", required=True)
        f_parser.add_argument("--activities", required=True)
        f_parser.add_argument("--snapshot", required=True)
        f_parser.add_argument("--activity", required=True)
        f_parser.add_argument("--day", type=int, required=True)
        f_parser.add_argument("--attempt-id")
        f_parser.add_argument("--manifest")
        f_parser.add_argument(
            "--model",
            choices=["custombkt", "pybkt"],
            default="custombkt",
            help="Mastery model: 'custombkt' (default) or 'pybkt'",
        )

    # Event recording commands: change-deadline
    for name in ("change-deadline", "record-deadline-change"):
        d_parser = subparsers.add_parser(name, parents=[common])
        d_parser.add_argument("--curriculum", required=True)
        d_parser.add_argument("--activities", required=True)
        d_parser.add_argument("--snapshot", required=True)
        d_parser.add_argument("--day", type=int, required=True)
        d_parser.add_argument("--new-deadline", type=int, required=True)
        d_parser.add_argument("--attempt-id")
        d_parser.add_argument("--manifest")
        d_parser.add_argument(
            "--model",
            choices=["custombkt", "pybkt"],
            default="custombkt",
            help="Mastery model: 'custombkt' (default) or 'pybkt'",
        )

    # Event recording commands: change-budget
    for name in ("change-budget", "record-budget-change"):
        b_parser = subparsers.add_parser(name, parents=[common])
        b_parser.add_argument("--curriculum", required=True)
        b_parser.add_argument("--activities", required=True)
        b_parser.add_argument("--snapshot", required=True)
        b_parser.add_argument("--day", type=int, required=True)
        b_parser.add_argument("--new-budget", type=int, required=True)
        b_parser.add_argument("--attempt-id")
        b_parser.add_argument("--manifest")
        b_parser.add_argument(
            "--model",
            choices=["custombkt", "pybkt"],
            default="custombkt",
            help="Mastery model: 'custombkt' (default) or 'pybkt'",
        )

    # Explicit legacy import/export commands
    imp_parser = subparsers.add_parser("import-legacy", parents=[common])
    imp_parser.add_argument("--curriculum", required=True)
    imp_parser.add_argument("--activities", required=True)
    imp_parser.add_argument("--learner", required=True)
    imp_parser.add_argument("--log", required=True)
    imp_parser.add_argument("--out-snapshot", required=True)
    imp_parser.add_argument("--goal")
    imp_parser.add_argument("--deadline", type=int)
    imp_parser.add_argument("--budget", type=int)
    imp_parser.add_argument("--manifest")

    exp_parser = subparsers.add_parser("export-legacy", parents=[common])
    exp_parser.add_argument("--curriculum", required=True)
    exp_parser.add_argument("--activities", required=True)
    exp_parser.add_argument("--snapshot", required=True)
    exp_parser.add_argument("--out-learner", required=True)
    exp_parser.add_argument("--out-log", required=True)
    exp_parser.add_argument("--manifest")

    # plan
    plan_parser = subparsers.add_parser("plan", parents=[common])
    plan_parser.add_argument("--curriculum", required=True)
    plan_parser.add_argument("--activities", required=True)
    plan_parser.add_argument("--snapshot")
    plan_parser.add_argument("--learner")
    plan_parser.add_argument("--log")
    plan_parser.add_argument("--goal")
    plan_parser.add_argument("--deadline", type=int)
    plan_parser.add_argument("--budget", type=int)
    plan_parser.add_argument("--current-day", type=int, default=1)
    plan_parser.add_argument("--manifest")
    plan_parser.add_argument("--json", action="store_true")
    plan_parser.add_argument(
        "--model",
        choices=["custombkt", "pybkt"],
        default="custombkt",
        help="Mastery model: 'custombkt' (default) or 'pybkt'",
    )

    # replan
    replan_parser = subparsers.add_parser("replan", parents=[common])
    replan_parser.add_argument("--curriculum", required=True)
    replan_parser.add_argument("--activities", required=True)
    replan_parser.add_argument("--learner")
    replan_parser.add_argument("--log")
    replan_parser.add_argument("--snapshot")
    replan_parser.add_argument("--goal")
    replan_parser.add_argument("--deadline", type=int)
    replan_parser.add_argument("--budget", type=int)
    replan_parser.add_argument("--current-day", type=int, default=1)
    replan_parser.add_argument("--manifest")
    replan_parser.add_argument("--json", action="store_true")
    replan_parser.add_argument(
        "--model",
        choices=["custombkt", "pybkt"],
        default="custombkt",
        help="Mastery model: 'custombkt' (default) or 'pybkt'",
    )

    # W8 K.4: A0 authoring aid (drafts only; approval needs a human via record_review.py)
    author = subparsers.add_parser("author", help="AI-assisted curriculum drafts (D54)")
    author_sub = author.add_subparsers(dest="author_cmd", required=True)
    a_draft = author_sub.add_parser("draft")
    a_draft.add_argument("--name", required=True)
    a_draft.add_argument("--topic", required=True)
    a_draft.add_argument("--concepts", type=int, default=3)
    a_draft.add_argument(
        "--provider", default="stub", help="stub | anthropic[:model] | ollama[:model]"
    )
    a_draft.add_argument("--cache", help="response cache directory (replays offline)")
    a_draft.add_argument("--drafts-root", default="data/drafts")
    a_val = author_sub.add_parser("validate")
    a_val.add_argument("--name", required=True)
    a_val.add_argument("--drafts-root", default="data/drafts")

    args = parser.parse_args(argv)
    if args.command == "author":
        return _author(args)

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
            return None

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
            return None

        elif args.command == "init-learner":
            out_path = args.snapshot or args.out
            if not out_path:
                raise ValidationError("init-learner requires --snapshot or --out")
            engine = Engine.from_files(
                args.curriculum,
                args.activities,
                manifest_path=args.manifest,
                allow_unreviewed=args.allow_unreviewed,
            )
            state = engine.init_learner()
            ctx = None
            if args.goal and args.deadline is not None and args.budget is not None:
                ctx = PlanContext(goal=args.goal, deadline_day=args.deadline, budget=args.budget)
            # Write canonical snapshot with empty log and optional context
            save_snapshot(state, ExecutionLog(), out_path, context=ctx)
            print(f"Created canonical snapshot file {out_path}")
            return None

        elif args.command == "update":
            engine = Engine.from_files(
                args.curriculum,
                args.activities,
                manifest_path=args.manifest,
                allow_unreviewed=args.allow_unreviewed,
                model=_resolve_model(getattr(args, "model", None)),
            )
            snap_ctx = None
            if args.snapshot:
                state, log, snap_ctx = load_snapshot(
                    args.snapshot, engine.graph.concepts(), include_context=True
                )
            elif args.learner and args.log:
                state = load_learner(args.learner, engine.graph.concepts())
                log = load_log(args.log)
            else:
                raise ValidationError("update requires --snapshot or (--learner and --log)")

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

            # Commit atomically through single snapshot replace
            if args.snapshot:
                save_snapshot(new_state, new_log, args.snapshot, context=snap_ctx)
            if args.save:
                if args.learner:
                    save_learner(new_state, args.learner)
                if args.log:
                    save_log(new_log, args.log)
            return None

        elif args.command in ("missed-day", "record-missed-day"):
            engine = Engine.from_files(
                args.curriculum,
                args.activities,
                manifest_path=args.manifest,
                allow_unreviewed=args.allow_unreviewed,
                model=_resolve_model(getattr(args, "model", None)),
            )
            state, log, snap_ctx = load_snapshot(
                args.snapshot, engine.graph.concepts(), include_context=True
            )
            event = Event(day=args.day, kind=EventType.MISSED, attempt_id=args.attempt_id)
            new_state, new_log = engine.record(state, log, event)
            save_snapshot(new_state, new_log, args.snapshot, context=snap_ctx)
            print(f"Recorded MISSED event for day {args.day} in {args.snapshot}")
            return None

        elif args.command in ("failed-assessment", "record-failed-assessment"):
            engine = Engine.from_files(
                args.curriculum,
                args.activities,
                manifest_path=args.manifest,
                allow_unreviewed=args.allow_unreviewed,
                model=_resolve_model(getattr(args, "model", None)),
            )
            state, log, snap_ctx = load_snapshot(
                args.snapshot, engine.graph.concepts(), include_context=True
            )
            activity = engine.activities.get(args.activity)
            if not activity:
                raise AdaptEngineError(f"Unknown activity {args.activity}")
            event = Event(
                day=args.day,
                kind=EventType.FAILED_ASSESSMENT,
                activity_id=args.activity,
                minutes_elapsed=activity.duration,
                correct=False,
                attempt_id=args.attempt_id,
            )
            new_state, new_log = engine.record(state, log, event)
            save_snapshot(new_state, new_log, args.snapshot, context=snap_ctx)
            print(f"Recorded FAILED_ASSESSMENT for {args.activity} on day {args.day}")
            return None

        elif args.command in ("change-deadline", "record-deadline-change"):
            engine = Engine.from_files(
                args.curriculum,
                args.activities,
                manifest_path=args.manifest,
                allow_unreviewed=args.allow_unreviewed,
                model=_resolve_model(getattr(args, "model", None)),
            )
            state, log, snap_ctx = load_snapshot(
                args.snapshot, engine.graph.concepts(), include_context=True
            )
            event = Event(
                day=args.day,
                kind=EventType.DEADLINE_CHANGED,
                value=args.new_deadline,
                attempt_id=args.attempt_id,
            )
            new_state, new_log = engine.record(state, log, event)
            save_snapshot(new_state, new_log, args.snapshot, context=snap_ctx)
            print(f"Recorded DEADLINE_CHANGED ({args.new_deadline}) on day {args.day}")
            return None

        elif args.command in ("change-budget", "record-budget-change"):
            engine = Engine.from_files(
                args.curriculum,
                args.activities,
                manifest_path=args.manifest,
                allow_unreviewed=args.allow_unreviewed,
                model=_resolve_model(getattr(args, "model", None)),
            )
            state, log, snap_ctx = load_snapshot(
                args.snapshot, engine.graph.concepts(), include_context=True
            )
            event = Event(
                day=args.day,
                kind=EventType.BUDGET_CHANGED,
                value=args.new_budget,
                attempt_id=args.attempt_id,
            )
            new_state, new_log = engine.record(state, log, event)
            save_snapshot(new_state, new_log, args.snapshot, context=snap_ctx)
            print(f"Recorded BUDGET_CHANGED ({args.new_budget}) on day {args.day}")
            return None

        elif args.command == "import-legacy":
            engine = Engine.from_files(
                args.curriculum,
                args.activities,
                manifest_path=args.manifest,
                allow_unreviewed=args.allow_unreviewed,
            )
            state = load_learner(args.learner, engine.graph.concepts())
            log = load_log(args.log)
            ctx = None
            if args.goal and args.deadline is not None and args.budget is not None:
                ctx = PlanContext(goal=args.goal, deadline_day=args.deadline, budget=args.budget)
            save_snapshot(state, log, args.out_snapshot, context=ctx)
            print(f"Imported legacy files into canonical snapshot {args.out_snapshot}")
            return None

        elif args.command == "export-legacy":
            engine = Engine.from_files(
                args.curriculum,
                args.activities,
                manifest_path=args.manifest,
                allow_unreviewed=args.allow_unreviewed,
            )
            state, log = load_snapshot(args.snapshot, engine.graph.concepts())
            save_learner(state, args.out_learner)
            save_log(log, args.out_log)
            print(f"Exported snapshot {args.snapshot} to {args.out_learner} and {args.out_log}")
            return None

        elif args.command == "plan":
            engine = Engine.from_files(
                args.curriculum,
                args.activities,
                manifest_path=args.manifest,
                allow_unreviewed=args.allow_unreviewed,
                model=_resolve_model(getattr(args, "model", None)),
            )
            state = None
            log = None
            snap_ctx = None
            if args.snapshot:
                state, log, snap_ctx = load_snapshot(
                    args.snapshot, engine.graph.concepts(), include_context=True
                )
            if state is None and args.learner:
                state = load_learner(args.learner, engine.graph.concepts())
            if log is None and args.log:
                log = load_log(args.log)
            if log is None:
                log = ExecutionLog()

            goal = args.goal or (snap_ctx.goal if snap_ctx else None)
            deadline = (
                args.deadline
                if args.deadline is not None
                else (snap_ctx.deadline_day if snap_ctx else None)
            )
            budget = (
                args.budget if args.budget is not None else (snap_ctx.budget if snap_ctx else None)
            )
            current_day = (
                args.current_day
                if args.current_day is not None
                else (snap_ctx.current_day if snap_ctx else 1)
            )

            if not goal or deadline is None or budget is None:
                raise ValidationError(
                    "plan requires goal, deadline, and budget (either via args or snapshot)"
                )

            done_ids = log.completed_ids()
            ctx = PlanContext(
                goal=goal,
                deadline_day=deadline,
                budget=budget,
                current_day=current_day,
            )
            plan_res = engine.plan(state, ctx, done_ids=done_ids)

            if args.json:
                print(json.dumps(serialize_plan(plan_res, engine.config), indent=2))
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

            if plan_res.status == PlanStatus.FEASIBLE:
                return None
            elif plan_res.status == PlanStatus.INFEASIBLE:
                return 1
            elif plan_res.status == PlanStatus.UNKNOWN:
                return 3
            return None

        elif args.command == "replan":
            engine = Engine.from_files(
                args.curriculum,
                args.activities,
                manifest_path=args.manifest,
                allow_unreviewed=args.allow_unreviewed,
                model=_resolve_model(getattr(args, "model", None)),
            )
            state = None
            log = None
            snap_ctx = None
            if args.snapshot:
                state, log, snap_ctx = load_snapshot(
                    args.snapshot, engine.graph.concepts(), include_context=True
                )
            if state is None and args.learner:
                state = load_learner(args.learner, engine.graph.concepts())
            if log is None and args.log:
                log = load_log(args.log)
            if log is None:
                log = ExecutionLog()

            goal = args.goal or (snap_ctx.goal if snap_ctx else None)
            deadline = (
                args.deadline
                if args.deadline is not None
                else (snap_ctx.deadline_day if snap_ctx else None)
            )
            budget = (
                args.budget if args.budget is not None else (snap_ctx.budget if snap_ctx else None)
            )
            current_day = (
                args.current_day
                if args.current_day is not None
                else (snap_ctx.current_day if snap_ctx else 1)
            )

            if not goal or deadline is None or budget is None:
                raise ValidationError(
                    "replan requires goal, deadline, and budget (either via args or snapshot)"
                )

            ctx = PlanContext(
                goal=goal,
                deadline_day=deadline,
                budget=budget,
                current_day=current_day,
            )
            plan_res = engine.replan(state, log, ctx)

            if args.json:
                print(json.dumps(serialize_plan(plan_res, engine.config), indent=2))
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

            if plan_res.status == PlanStatus.FEASIBLE:
                return None
            elif plan_res.status == PlanStatus.INFEASIBLE:
                return 1
            elif plan_res.status == PlanStatus.UNKNOWN:
                return 3
            return None

    except AdaptEngineError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2


def _author(args) -> int:
    import os

    from .authoring.checks import validate_draft
    from .authoring.draft import generate_draft
    from .authoring.providers import ProviderError, make_provider

    if args.author_cmd == "validate":
        rep = validate_draft(os.path.join(args.drafts_root, args.name), args.name).to_dict()
        print(json.dumps(rep, indent=2))
        return 0 if rep["ok"] else 1
    try:
        provider = make_provider(args.provider, cache_dir=args.cache)
        res = generate_draft(
            provider,
            name=args.name,
            topic=args.topic,
            n_concepts=args.concepts,
            drafts_root=args.drafts_root,
        )
    except (ProviderError, ValueError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    print(json.dumps(res, indent=2))
    print(
        "Draft written for review. Approve with: python scripts/record_review.py "
        f"--promote-draft {args.name} --reviewer '<your name>'",
        file=sys.stderr,
    )
    return 0 if res["report"]["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
