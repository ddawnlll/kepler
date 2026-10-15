"""CLI adapter only. The scientific library never depends on experiment modules."""
import argparse

def main():
    parser = argparse.ArgumentParser(prog="python -m kepler.intelligence")
    parser.add_argument("command", choices=("atlas",))
    args, rest = parser.parse_known_args()
    if args.command == "atlas":
        # This executable adapter intentionally delegates to a frozen experiment.
        from experiments.erf01.atlas import main as run_atlas
        import sys
        sys.argv = [sys.argv[0], *rest]
        run_atlas()

if __name__ == "__main__":
    main()
