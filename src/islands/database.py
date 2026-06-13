import sqlite3
from pathlib import Path

from islands.models import Episode

DEFAULT_DB_PATH = Path("islands.db")

SCHEMA = """
CREATE TABLE IF NOT EXISTS episodes (
    guid TEXT PRIMARY KEY,
    podcast_id TEXT NOT NULL,
    title TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    pub_date TEXT NOT NULL DEFAULT '',
    source_audio_url TEXT NOT NULL,
    transcript_url TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'discovered'
        CHECK (status IN ('discovered', 'processing', 'completed', 'failed')),
    output_r2_key TEXT,
    output_url TEXT
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


def write_new_episode(
    conn: sqlite3.Connection,
    guid: str,
    podcast_id: str,
    title: str,
    description: str,
    pub_date: str,
    source_audio_url: str,
    transcript_url: str,
) -> None:
    episode = Episode(
        guid=guid,
        title=title,
        description=description,
        pub_date=pub_date,
        mp3_url=source_audio_url,
        transcript_url=transcript_url,
    )
    write_new_episodes(conn, podcast_id, [episode])


def write_new_episodes(
    conn: sqlite3.Connection,
    podcast_id: str,
    episodes: list[Episode],
) -> None:
    conn.executemany(
        """
        INSERT OR IGNORE INTO episodes (
            guid,
            podcast_id,
            title,
            description,
            pub_date,
            source_audio_url,
            transcript_url,
            status
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, 'discovered')
        """,
        [
            (
                ep.guid,
                podcast_id,
                ep.title,
                ep.description,
                ep.pub_date,
                ep.mp3_url,
                ep.transcript_url,
            )
            for ep in episodes
        ],
    )
    conn.commit()


def write_episode_status(conn: sqlite3.Connection, guid: str, status: str) -> None:
    conn.execute(
        """
        UPDATE episodes
        SET status = ?
        WHERE guid = ?
    """,
        (status, guid),
    )
    conn.commit()
