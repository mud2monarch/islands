import logging
import urllib.request

from rich.logging import RichHandler

from process import filter_n_episodes, strip_episode

FEED_URL = "https://omny.fm/shows/bloomberg-surveillance/playlists/podcast.rss"

logging.basicConfig(
    level=logging.INFO,
    format="%(message)s",
    handlers=[
        RichHandler(
            rich_tracebacks=True,
            log_time_format="[%m/%d/%y %H:%M:%S.%f]",
        )
    ],
)


def main():
    with urllib.request.urlopen(FEED_URL) as feed:
        episodes = filter_n_episodes(
            feed=feed,
            num_episodes=2,
        )

    logging.info(f"Found {len(episodes)} matching episodes.")

    for ep in episodes:
        output_path = strip_episode(ep)
        logging.info(f"Wrote ad-free episode to {output_path}.")


if __name__ == "__main__":
    main()
