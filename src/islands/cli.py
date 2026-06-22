import argparse


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="islands",
        description="Strip ads from podcast episodes.",
    )
    parser.add_argument(
        "--feed-url",
        help="RSS feed URL to process.",
    )
    parser.add_argument(
        "--num-episodes",
        type=int,
        default=2,
        help="Number of recent RSS items to scan.",
    )
    return parser.parse_args()


"""
Default use is to run

uv run islands --date 2026-06-12

and it auto-discovers your rss_link, refs, and text_references per-directory

"""
