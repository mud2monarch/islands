import argparse

from islands.main import FEED_URL


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="islands",
        description="Strip ads from podcast episodes.",
    )
    parser.add_argument(
        "--feed-url",
        default=FEED_URL,
        help="RSS feed URL to process.",
    )
    parser.add_argument(
        "--num-episodes",
        type=int,
        default=2,
        help="Number of recent RSS items to scan.",
    )
    return parser.parse_args()
