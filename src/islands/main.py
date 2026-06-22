import logging
import os
from datetime import date
from pathlib import Path

from dotenv import load_dotenv
from rich.logging import RichHandler

from islands.audio import build_clip_references, get_duration
from islands.database import init as database_init
from islands.database import (
    write_new_episode,
    write_new_podcast,
)
from islands.models import ReadyForProcessing, SurveillanceKind
from islands.network import get_public_object_url, upload_episode, upload_rss_feed
from islands.process import strip_episode
from islands.rss import (
    get_n_new_episodes,
    get_podcast_info,
    make_surveillance_kind_filter,
    write_rss_feed,
)

load_dotenv()
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

    RSS_PREFIX = os.getenv("RSS_PREFIX")
    WSW_FEED = "https://omny.fm/shows/wall-street-week/playlists/podcast.rss"
    SURVEILLANCE_FEED = (
        "https://omny.fm/shows/bloomberg-surveillance/playlists/podcast.rss"
    )

    wsw = get_podcast_info(WSW_FEED)
    wsw.text_references, wsw.audio_references = build_clip_references(
        Path("reference/surveillance")
    )
    wsw_episodes = get_n_new_episodes(
        podcast=wsw,
        # episode_filter=make_surveillance_kind_filter(SurveillanceKind.TK_CANDIDATE),
        start_date=date(2026, 6, 13),
        conn=conn,
        num_episodes=3,
    )

    if len(wsw_episodes) > 0:
        queue.append(ReadyForProcessing(episodes=wsw_episodes, podcast=wsw))
    else:
        logging.warning(f"No new episodes to process for podcast {wsw.title}.")

    for item in queue:
        write_new_podcast(conn, item.podcast)

        for ep in item.episodes:
            output_path = strip_episode(ep, item.podcast)
            if output_path is None:
                logging.warning(f"Failed to process, {ep.title} skipping.")
                continue
            logging.info(f"Wrote ad-free episode to {output_path}.")

            duration = get_duration(output_path)
            file_size_bytes = output_path.stat().st_size

            episode_key = upload_episode(output_path, ep)

            write_new_episode(conn, ep, episode_key, duration, file_size_bytes)

        rss_feed = write_rss_feed(conn, item.podcast)
        logging.info(f"Wrote RSS feed to {rss_feed}.")

        rss_key = upload_rss_feed(rss_feed, prefix=RSS_PREFIX)
        logging.info(f"Uploaded RSS feed to {get_public_object_url(rss_key)}.")


if __name__ == "__main__":
    main()
