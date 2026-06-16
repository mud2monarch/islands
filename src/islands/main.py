import logging
from pathlib import Path

from rich.logging import RichHandler

from islands.audio import build_clip_references, get_duration
from islands.database import init as database_init
from islands.database import (
    write_new_episode,
    write_new_podcast,
)
from islands.models import ReadyForProcessing, SurveillanceKind
from islands.network import upload_episode
from islands.process import strip_episode
from islands.rss import (
    get_n_new_episodes,
    get_podcast_info,
    make_surveillance_kind_filter,
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
    wsw_episodes = get_n_new_episodes(
        podcast=wsw,
        conn=conn,
        num_episodes=1,
    )

    if len(wsw_episodes) > 0:
        queue.append(ReadyForProcessing(episodes=wsw_episodes, podcast=wsw))
    else:
        logging.warning(f"No new episodes to process for podcast {wsw.title}.")

    for item in queue:
        write_new_podcast(conn, item.podcast)

        for ep in item.episodes:
            output_path = strip_episode(ep, item.podcast)
            logging.info(f"Wrote ad-free episode to {output_path}.")

            duration = get_duration(output_path)
            bytes = output_path.stat().st_size

            storage_key = upload_episode(output_path, ep)

            write_new_episode(conn, ep, storage_key, duration, bytes)


if __name__ == "__main__":
    main()
