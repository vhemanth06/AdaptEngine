import sys
import argparse
from .api import Engine
from .session import load_learner, save_learner, load_log, save_log
from .core.errors import AdaptEngineError
from .core.schema import Event, EventType


def main(argv=None):
    if argv is None:
        argv = sys.argv[1:]

    parser = argparse.ArgumentParser(prog="adaptengine")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # validate
    val_parser = subparsers.add_parser("validate")
    val_parser.add_argument("--curriculum", required=True)
    val_parser.add_argument("--activities", required=True)
    val_parser.add_argument("--allow-unreviewed", action="store_true")

    # show
    show_parser = subparsers.add_parser("show")
    show_parser.add_argument("--curriculum", required=True)

    # init-learner
    init_parser = subparsers.add_parser("init-learner")
    init_parser.add_argument("--curriculum", required=True)
    init_parser.add_argument("--out", required=True)

    # update
    upd_parser = subparsers.add_parser("update")
    upd_parser.add_argument("--curriculum", required=True)
    upd_parser.add_argument("--activities", required=True)
    upd_parser.add_argument("--learner", required=True)
    upd_parser.add_argument("--log", required=True)
    upd_parser.add_argument("--activity", required=True)
    upd_parser.add_argument("--response", choices=["correct", "incorrect"])
    upd_parser.add_argument("--day", type=int, required=True)
    upd_parser.add_argument("--save", action="store_true")

    args = parser.parse_args(argv)

    try:
        if args.command == "validate":
            if args.allow_unreviewed:
                print("Warning: allowing unreviewed content", file=sys.stderr)
            engine = Engine.from_files(
                args.curriculum, args.activities, allow_unreviewed=args.allow_unreviewed
            )
            print(
                f"OK: {len(engine.graph.concepts())} concepts, {len(engine.activities)} activities (reviewed)"
            )

        elif args.command == "show":
            engine = Engine.from_files(
                args.curriculum, "data/curriculum/activities_4node.json", allow_unreviewed=True
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
                args.curriculum, "data/curriculum/activities_4node.json", allow_unreviewed=True
            )
            state = engine.init_learner()
            save_learner(state, args.out)
            print(f"Created learner file {args.out}")

        elif args.command == "update":
            engine = Engine.from_files(args.curriculum, args.activities, allow_unreviewed=True)
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
    except AdaptEngineError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
