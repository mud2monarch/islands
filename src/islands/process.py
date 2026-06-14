import logging
import sqlite3
import subprocess
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

import librosa
import numpy as np
from rapidfuzz import fuzz

from islands.database import write_new_episodes

from .analysis import find_similar_mel_ts
from .models import (
    Episode,
    EpisodeFilter,
    MediaKind,
    Podcast,
    SurveillanceKind,
    TranscriptKind,
)

logger = logging.getLogger(__name__)

VALID_AUDIO_SUFFIXES = {".mp3", ".wav", ".m4a", ".ogg", ".flac"}
SAMPLE_RATE = 22050
MEL_HOP_LENGTH = 512
MEL_FPS = SAMPLE_RATE / MEL_HOP_LENGTH

OPENING_TRANSCRIPT = "speaker 1: bloomberg audio studios, podcasts, radio news. this is the bloomberg surveillance podcast. catch us live weekdays at seven am eastern on apple car play"

RETURN_TRANSCRIPT = "speaker 1: you're listening to the bloomberg surveillance podcast. catch us live weekday afternoons from seven to ten am eastern listen on apple karplay"

NAMESPACES = {
    "media": "http://search.yahoo.com/mrss/",
    "podcast": "https://podcastindex.org/namespace/1.0",
}


def build_clip_references(directory: Path) -> tuple[list[str], list[np.ndarray]]:
    """Build audio and text into a set of references for ad identification

    args:
        path: the path to the directory with audio files and a single text file
    returns:
        list of audio and text references
    """
    text_references: list[str] = []
    audio_mels: list[np.ndarray] = []

    if not directory.is_dir():
        raise ValueError(f"Expected a directory at {directory}")

    for path in directory.iterdir():
        if path.suffix.lower() == ".txt":
            file = open(path, "r")
            text = file.read()
            text_references = text.strip().split("\n")
        elif path.suffix.lower() in VALID_AUDIO_SUFFIXES:
            audio_mels.append(load_mel(path))

    return text_references, audio_mels


def load_mel(path: Path) -> np.ndarray:
    """load a mel spectrogram from a file

    args:
        path: the path to the audio file.
    """
    if path.suffix.lower() not in VALID_AUDIO_SUFFIXES:
        raise ValueError(f"Invalid audio file: {path}")

    y, _ = librosa.load(path)
    return librosa.feature.melspectrogram(
        y=y, sr=SAMPLE_RATE, hop_length=MEL_HOP_LENGTH
    )


def make_surveillance_kind_filter(kind: SurveillanceKind) -> EpisodeFilter:
    """Meta-function to filter elements based on SurveillanceKind

    args:
        kind: the SurveillanceKind for which you want to filter
    returns:
        an EpisodeFilter function
    """

    def episode_matches_kind(item: ET.Element) -> bool:
        title = item.findtext("title", "")
        return guess_surveillance_kind(title) == kind

    return episode_matches_kind


def guess_surveillance_kind(title: str) -> SurveillanceKind:
    """Guess at the kind of episode based on parts of the episode title.

    Args:
        title: Title of the episode

    Returns:
        Match to a SurveillanceKind.

    TK_CANDIDATE is a *guess* because there is no brand identifier in the title of Tom Keene's radio show, while the other variants of Surveillance do have identifiers.
    """
    if "Bloomberg Surveillance TV" in title:
        return SurveillanceKind.FERRO

    if "Single Best Idea" in title or "Tom Keene" in title:
        return SurveillanceKind.TK_IDEA

    if "The Money Show" in title:
        return SurveillanceKind.MONEY

    return SurveillanceKind.TK_CANDIDATE


def get_podcast_info(rss_url: str) -> Podcast:
    """Parse Podcast metadata from an RSS feed

    args:
        rss_url: the RSS feed identifying a podcast
    returns:
        A built Podcast object less reference clips
    """
    with urllib.request.urlopen(rss_url) as feed:
        tree = ET.parse(feed)
    root = tree.getroot()

    title = root.findtext("./channel/title", "")
    description = root.findtext("./channel/description", "")
    pfp_url = root.findtext("./channel/image/url", "")

    return Podcast(
        title,
        description,
        pfp_url,
        rss_url,
        text_references=[],
        audio_references=[],
    )


def filter_n_episodes(
    podcast: Podcast,
    conn: sqlite3.Connection,
    episode_filter: EpisodeFilter | None = None,
    num_episodes: int = 2,
) -> list[Episode]:
    """Get n Episodes from a podcast

    Args:
        podcast: the Podcast you want to parse
        conn: connection to the database
        episode_filter: any predicate you'd like to meet
        num_episodes: number of matching episodes to find
    """
    desired_episodes: list[Episode] = []

    with urllib.request.urlopen(podcast.rss_url) as feed:
        tree = ET.parse(feed)
    root = tree.getroot()

    for item in root.findall("./channel/item"):
        if len(desired_episodes) >= num_episodes:
            break

        if episode_filter is not None and not episode_filter(item):
            continue

        guid = item.findtext("guid", "").strip()
        if not guid:
            raise ValueError("guid is required")

        title = item.findtext("title", "")
        description = item.findtext("description", "")
        pub_date = item.findtext("pubDate", "")
        mp3_link = None
        transcript_url = None

        for media in item.findall("media:content", NAMESPACES):
            if media.attrib.get("type") == MediaKind.AUDIO.value:
                mp3_link = media.attrib.get("url")

        for transcript in item.findall("podcast:transcript", NAMESPACES):
            if transcript.attrib.get("type") == TranscriptKind.TEXT.value:
                transcript_url = transcript.attrib.get("url")

        if mp3_link is not None and transcript_url is not None:
            desired_episodes.append(
                Episode(guid, title, description, pub_date, mp3_link, transcript_url)
            )

    write_new_episodes(conn, podcast.title, desired_episodes)

    return desired_episodes


def ts_to_int(text_ts: str) -> int:
    """Trivial conversion of a podcast timestamp, in the form of HH:MM:SS, to number of seconds.

    Args:
        text_ts: Text timestamp
    Returns:
        Number of seconds
    """
    try:
        h, m, s = text_ts.split(":")
        return int(h) * 3600 + int(m) * 60 + int(s)
    except ValueError as exc:
        raise ValueError(f"Invalid timestamp: {text_ts!r}") from exc


def int_to_ts(seconds: int) -> str:
    """Trivial conversion of a number of seconds to a podcast timestamp, in the form of HH:MM:SS.

    Args:
        seconds: number of seconds
    Returns:
        Text timestamp in format HH:MM:SS
    """
    if seconds < 0:
        raise ValueError("seconds must be non-negative")

    h, remainder = divmod(seconds, 3600)
    m, s = divmod(remainder, 60)

    return f"{h:02d}:{m:02d}:{s:02d}"


def clip_audio(
    start_secs: int,
    duration_secs: int,
    path: str,
    output: str,
):
    """Call out to ffmpeg CLI to slice an audio file

    Args:
        start_secs: number of whole seconds when you want to start the clip
        duration_secs: duration of the clip, in whole seconds
        path: path of the file you want to clip
        output: path to intended output
    Returns:
        Nothing. Executes process on the machine.
    """
    Path(output).parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-ss",
            int_to_ts(start_secs),
            "-t",
            int_to_ts(duration_secs),
            "-i",
            path,
            "-ac",
            "1",
            "-ar",
            "22050",
            "-acodec",
            "pcm_s16le",
            output,
        ],
        check=True,
    )


def merge_clips(dir: str, num_cuts: int, output: str):
    """Call out to ffmpeg to merge files in a directory.

    Args:
        dir: path to directory of clips you want to merge
        num_cuts: number of clips you want to merge. Assumes the clips are named as "cut_{i}.wav". Will look for clips starting at 0 index.
        output: output filepath
    Returns:
        Nothing. Executes process on machine.
    """
    cuts_dir = Path(dir)
    concat_file = cuts_dir / "cuts.txt"

    Path(output).parent.mkdir(parents=True, exist_ok=True)
    concat_file.write_text("".join(f"file 'cut_{i}.wav'\n" for i in range(num_cuts)))

    subprocess.run(
        [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            str(concat_file),
            "-ac",
            "1",
            "-ar",
            "22050",
            "-codec:a",
            "libmp3lame",
            "-b:a",
            "64k",
            output,
        ],
        check=True,
    )


def chunk_transcript(
    transcript: str,
) -> list[tuple[int, str]]:
    """Splits transcript into a list of timestamps and text chunks. Assumes well-formatted transcripts

    Args:
        transcript: a single block of text in plaintext transcript format

    Returns:
        A list of (int, str) where int is the number of whole seconds of the timestamp and str is the text of the transcript for that chunk.
    """
    chunks = []
    blocks = transcript.strip().lower().split("\n\n")

    for block in blocks:
        ts, text = block.strip().split("\n")
        chunks.append((ts_to_int(ts), text))

    return chunks


def download_audio(url: str, output_path: Path) -> Path:
    """Trivial function to save remote audio to local machine

    Args:
        url: URL of the audio file to download
        output_path: destination path for the audio file

    Returns:
        The path to the downloaded audio file
    """
    logger.info(f"Downloading audio from {url} to {output_path}.")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    urllib.request.urlretrieve(url, output_path)
    return output_path


def fetch_text(url: str) -> str:
    """Trivial function to get plaintext from a URL

    Args:
        url: URL of the text file to fetch

    Returns:
        The plaintext content of the URL
    """
    with urllib.request.urlopen(url) as response:
        return response.read().decode("utf-8")


def fuzzy_contains_phrase(
    target_text: str,
    reference_phrase: str,
    threshold: float | int = 85,
) -> bool:
    """Search a piece of text to see if it contains a reference phrase

    args:
        target_text: target text to test
        reference_phrase: phrase for which you're looking. Should be all lowercase
        threshold: value between 0 and 100, higher is more similar
    returns:
        whether target_text contains reference_phrase
    """
    words = target_text.strip().lower().split()
    phrase_len = len(reference_phrase.strip().split())

    for i in range(len(words) - phrase_len + 1):
        window = " ".join(words[i : i + phrase_len])
        if fuzz.ratio(window, reference_phrase) >= threshold:
            return True

    return False


def strip_episode(episode: Episode, podcast: Podcast) -> str:
    """Function to strip ads from an Episode

    Args:
        episode: Episode you want to strip
        references: set of ClipReferences against which to match
    Returns:
        Filepath to the output file
    """

    MEL_MATCH_CONFIDENCE = 0.6
    TEST_CLIP_SECONDS = 240

    audio_path = download_audio(
        episode.mp3_url, Path(f"output/dirty/episodes/{episode.title}.mp3")
    )
    cumulative_ads: int = 0
    ad_spans: list[int] = []
    end_ts: int = 0
    candidates: list[int] = []

    chunks = chunk_transcript(fetch_text(episode.transcript_url))
    for i, chunk in enumerate(chunks):
        ts, text = chunk

        if any(
            fuzzy_contains_phrase(text, phrase) for phrase in podcast.text_references
        ):
            candidates.append(ts)

        if i == len(chunks) - 1:
            end_ts = ts

    logger.info(f"found {len(candidates)} candidates")
    if len(candidates) == 0:
        raise ValueError("no candidates found")

    return_timestamps: list[int] = []

    for i, ts in enumerate(candidates):
        previous_cumulative_ads = cumulative_ads
        clip_start = max(ts + cumulative_ads - 5, 0)

        logger.info(
            f"processing candidate {i}, starting clip at {int_to_ts(clip_start)}. accumulated ad time is {int_to_ts(cumulative_ads)}"
        )

        clip_audio(
            clip_start,
            TEST_CLIP_SECONDS,
            str(audio_path),
            f"output/dirty/comparison/clip_{i}.wav",
        )

        clip_y, _ = librosa.load(f"output/dirty/comparison/clip_{i}.wav")
        clip_mel = librosa.feature.melspectrogram(
            y=clip_y, sr=SAMPLE_RATE, hop_length=MEL_HOP_LENGTH
        )

        return_secs: int
        confidence: float

        matches = [
            find_similar_mel_ts(clip_mel, ref_mel, MEL_FPS)
            for ref_mel in podcast.audio_references
        ]
        return_secs, confidence = max(matches, key=lambda match: match[1])

        real_ts = clip_start + return_secs

        if confidence > MEL_MATCH_CONFIDENCE:
            # Register the new return point
            return_timestamps.append(real_ts)
            # Update the total drift in timestamps
            cumulative_ads = real_ts - ts
            # Register the length of the ad break
            ad_spans.append(cumulative_ads - previous_cumulative_ads)
        else:
            logger.warning(
                f"confidence ({confidence}) below threshold, skipping. Window was at {int_to_ts(real_ts)}"
            )

    end_ts += cumulative_ads

    for i, stamp in enumerate(return_timestamps):
        if i == len(return_timestamps) - 1:
            logger.info(
                f"Clipping {end_ts - stamp} seconds starting at {int_to_ts(stamp)}."
            )
            clip_audio(
                stamp,
                end_ts - stamp,
                str(audio_path),
                f"output/dirty/cuts/cut_{i}.wav",
            )
        else:
            logger.info(
                f"Clipping {return_timestamps[i + 1] - return_timestamps[i] - ad_spans[i + 1]} seconds starting at {int_to_ts(stamp)}."
            )
            clip_audio(
                stamp,
                return_timestamps[i + 1] - return_timestamps[i] - ad_spans[i + 1],
                str(audio_path),
                f"output/dirty/cuts/cut_{i}.wav",
            )

    logger.info("Merging clips...")

    output_path = f"output/clean/{episode.title}_clean.mp3"

    merge_clips(
        "output/dirty/cuts",
        len(return_timestamps),
        output_path,
    )
    logger.info("Done merging.")

    return output_path
