import logging
from pathlib import Path

from rich.logging import RichHandler

from islands.database import init as database_init
from islands.models import ReadyForProcessing, SurveillanceKind
from islands.process import (
    build_clip_references,
    filter_n_episodes,
    get_podcast_info,
    make_surveillance_kind_filter,
    strip_episode,
)

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
    conn = database_init()
    queue: list[ReadyForProcessing] = []

    # Podcast construction
    surveillance = get_podcast_info(
        "https://omny.fm/shows/bloomberg-surveillance/playlists/podcast.rss"
    )
    surveillance.clip_references = build_clip_references(
        Path("../reference/surveillance")
    )
    surveillance_filter = make_surveillance_kind_filter(SurveillanceKind.TK_CANDIDATE)
    surveillance_episodes = filter_n_episodes(
        podcast=surveillance,
        conn=conn,
        episode_filter=surveillance_filter,
        num_episodes=3,
    )

    queue.append(
        ReadyForProcessing(episodes=surveillance_episodes, podcast=surveillance)
    )

    logging.info(f"Found {len(surveillance_episodes)} matching episodes.")

    for item in queue:
        for ep in item.episodes:
            output_path = strip_episode(ep, item.podcast.clip_references)
            logging.info(f"Wrote ad-free episode to {output_path}.")


if __name__ == "__main__":
    main()
