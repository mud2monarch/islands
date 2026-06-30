import logging
import os
from pathlib import Path

from dotenv import load_dotenv
from rich.logging import RichHandler

from islands.audio import build_clip_references, get_duration
from islands.config import load_podcast_config
from islands.database import init as database_init
from islands.database import (
    write_new_episode,
    write_new_podcast,
)
from islands.filters import generate_filter
from islands.models import PodcastReference, ReadyForProcessing
from islands.network import get_public_object_url, upload_episode, upload_rss_feed
from islands.process import strip_episode
from islands.rss import (
    get_n_new_episodes,
    get_podcast_info,
    write_rss_feed,
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
    REFERENCES_DIRECTORY = Path("reference/")
    load_dotenv()
    RSS_PREFIX = os.getenv("RSS_PREFIX")
    conn = database_init()
    podcast_refs: list[PodcastReference] = []
    queue: list[ReadyForProcessing] = []

    if not REFERENCES_DIRECTORY.is_dir():
        raise ValueError("Expected a directory at references/")

    for subdir in REFERENCES_DIRECTORY.iterdir():
        if subdir.is_dir():
            for path in subdir.iterdir():
                if path.suffix.lower() == ".toml":
                    podcast_refs.append(
                        PodcastReference(config=load_podcast_config(path), path=subdir)
                    )

    for ref in podcast_refs:
        podcast = get_podcast_info(ref.config.rss_url)
        podcast.text_references, podcast.audio_references = build_clip_references(
            ref.path
        )
        episodes = get_n_new_episodes(
            podcast=podcast,
            conn=conn,
            start_date=ref.config.start_date,
            episode_filter=generate_filter(ref.config.filter),
        )
        if len(episodes) > 0:
            queue.append(ReadyForProcessing(episodes=episodes, podcast=podcast))
        else:
            logging.warning(f"No new episodes to process for podcast {podcast.title}.")

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
