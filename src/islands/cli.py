import argparse
from datetime import date


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="islands",
        description="Strip ads from podcast episodes.",
    )
    parser.add_argument(
        "--start",
        type=date.fromisoformat,
        dest="start_date",
        help="Starting date down to which you want to parse",
    )
    return parser.parse_args()


"""
Default use is to run

uv run islands --start 2026-06-12

and it auto-discovers your rss_link, refs, and text_references per-directory

"""
