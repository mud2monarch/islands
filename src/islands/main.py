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
    # surveillance = get_podcast_info(
    #     "https://omny.fm/shows/bloomberg-surveillance/playlists/podcast.rss"
    # )
    # surveillance.text_references, surveillance.audio_references = build_clip_references(
    #     Path("../reference/surveillance")
    # )
    # surveillance_filter = make_surveillance_kind_filter(SurveillanceKind.TK_CANDIDATE)
    # surveillance_episodes = filter_n_episodes(
    #     podcast=surveillance,
    #     conn=conn,
    #     episode_filter=surveillance_filter,
    #     num_episodes=3,
    # )

    wsw = get_podcast_info(
        "https://www.omnycontent.com/d/playlist/e73c998e-6e60-432f-8610-ae210140c5b1/3441857d-10f0-47c5-991f-ae3c0021f233/9040f928-9636-419d-8ac6-ae3c0021f241/podcast.rss"
    )
    wsw.text_references, wsw.audio_references = build_clip_references(
        Path("reference/wsw")
    )
    wsw_episodes = filter_n_episodes(
        podcast=wsw,
        conn=conn,
        num_episodes=1,
    )

    queue.append(ReadyForProcessing(episodes=wsw_episodes, podcast=wsw))

    for item in queue:
        for ep in item.episodes:
            output_path = strip_episode(ep, item.podcast)
            logging.info(f"Wrote ad-free episode to {output_path}.")


if __name__ == "__main__":
    main()
