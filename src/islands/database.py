import logging
import sqlite3
from pathlib import Path

from islands.models import Episode, EpisodeForRss, Podcast

logger = logging.getLogger(__name__)

DEFAULT_DB_PATH = Path("islands.db")

SCHEMA = """
CREATE TABLE IF NOT EXISTS episodes (
    podcast_rss_url TEXT NOT NULL,
    guid TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    pub_date TEXT NOT NULL DEFAULT '',
    source_audio_url TEXT NOT NULL,
    transcript_url TEXT NOT NULL DEFAULT '',
    output_bucket_key TEXT NOT NULL,
    duration TEXT NOT NULL,
    file_size_bytes INTEGER NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS podcasts(
    rss_url TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    pfp_url TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
"""


def connect(db_path: str | Path = DEFAULT_DB_PATH) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    return conn


def init(db_path: str | Path = DEFAULT_DB_PATH) -> sqlite3.Connection:
    db_path = Path(db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)

    conn = connect(db_path)
    conn.executescript(SCHEMA)
    conn.commit()
    return conn


def write_new_podcast(conn: sqlite3.Connection, podcast: Podcast) -> None:
    conn.execute(
        """
        INSERT INTO podcasts (
            rss_url,
            title,
            description,
            pfp_url
        )
        VALUES (?, ?, ?, ?)
        ON CONFLICT(rss_url) DO UPDATE SET
            title = excluded.title,
            description = excluded.description,
            pfp_url = excluded.pfp_url,
            updated_at = CURRENT_TIMESTAMP
        """,
        (
            podcast.rss_url,
            podcast.title,
            podcast.description,
            podcast.pfp_url,
        ),
    )
    conn.commit()


def write_new_episode(
    conn: sqlite3.Connection,
    episode: Episode,
    bucket_key: str,
    duration: str,
    file_size_bytes: int,
) -> None:
    conn.execute(
        """
        insert into episodes(
            podcast_rss_url,
            guid,
            title,
            description,
            pub_date,
            source_audio_url,
            transcript_url,
            output_bucket_key,
            duration,
            file_size_bytes
        )
        values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            episode.podcast.rss_url,
            episode.guid,
            episode.title,
            episode.description,
            episode.pub_date,
            episode.mp3_url,
            episode.transcript_url,
            bucket_key,
            duration,
            file_size_bytes,
        ),
    )
    conn.commit()

    logger.info(f"Wrote new episode {episode.guid} to database.")


def get_all_episode_guids(conn: sqlite3.Connection, podcast: Podcast) -> set[str]:
    """Retrieve all guids for a given podcast.

    args:
        - conn: The database connection.
        - podcast: The Podcast to retrieve guids for.
    returns:
        Set of all guids for the given Podcast.
    """
    rows = conn.execute(
        """
            select
                guid
            from episodes
            where podcast_rss_url = ?
        """,
        (podcast.rss_url,),
    ).fetchall()
    return {row["guid"] for row in rows}


def get_rss_relevant_episode_details(
    conn: sqlite3.Connection, podcast: Podcast
) -> list[EpisodeForRss]:
    """Retrieve all episodes for a podcast, prepared for RSS feed writing

    args:
        - conn: The database connection.
        - podcast: The Podcast to retrieve episodes for.
    returns:
        List of EpisodeForRss objects for the given Podcast.
    """
    episodes: list[EpisodeForRss] = []

    rows = conn.execute(
        """
            select
                guid,
                title,
                description,
                pub_date,
                output_bucket_key,
                duration,
                file_size_bytes
            from episodes
            where podcast_rss_url = ?
            order by created_at asc
        """,
        (podcast.rss_url,),
    ).fetchall()

    for row in rows:
        episodes.append(
            EpisodeForRss(
                guid=row["guid"],
                title=row["title"],
                description=row["description"],
                pub_date=row["pub_date"],
                output_bucket_key=row["output_bucket_key"],
                duration=row["duration"],
                file_size_bytes=row["file_size_bytes"],
            )
        )

    return episodes
