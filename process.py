import logging
import subprocess
import urllib.request
import xml.etree.ElementTree as ET
from enum import Enum
from pathlib import Path
from typing import IO

import librosa
from rapidfuzz import fuzz

from analysis import find_similar_mel_ts

logger = logging.getLogger(__name__)

SAMPLE_RATE = 22050
MEL_HOP_LENGTH = 512
MEL_FPS = SAMPLE_RATE / MEL_HOP_LENGTH

OPENING_TRANSCRIPT = "speaker 1: bloomberg audio studios, podcasts, radio news. this is the bloomberg surveillance podcast. catch us live weekdays at seven am eastern on apple car play"

RETURN_TRANSCRIPT = "speaker 1: you're listening to the bloomberg surveillance podcast. catch us live weekday afternoons from seven to ten am eastern listen on apple karplay"

NAMESPACES = {
    "media": "http://search.yahoo.com/mrss/",
    "podcast": "https://podcastindex.org/namespace/1.0",
}


class Episode:
    def __init__(self, title, description, pub_date, mp3_link, transcript_link):
        self.title: str = title
        self.description: str = description
        self.pub_date: str = pub_date
        self.mp3: str = mp3_link
        self.transcript: str = transcript_link


class SurveillanceKind(Enum):
    FERRO = "ferro"
    TK_IDEA = "tk_idea"
    MONEY = "money"
    TK_CANDIDATE = "tk"


class MediaKind(Enum):
    AUDIO = "audio/mpeg"
    JPEG = "image/jpeg"


class TranscriptKind(Enum):
    VTT = "text/vtt"
    SRT = "application/srt"
    TEXT = "text/plain"


def guess_title(title: str) -> SurveillanceKind:
    """Guess at the kind of episode based on parts of the episode title.

    Args:
        title: Title of the episode

    Returns:
        Match to a SurveillanceKind.

    TK_CANDIDATE is a guess because there is no brand identifier in the title of Tom Keene's radio show, while the other variants of Surveillance do have identifiers.
    """
    if "Bloomberg Surveillance TV" in title:
        return SurveillanceKind.FERRO

    if "Single Best Idea" in title or "Tom Keene" in title:
        return SurveillanceKind.TK_IDEA

    if "Bloomberg Money" in title:
        return SurveillanceKind.MONEY

    return SurveillanceKind.TK_CANDIDATE


def filter_n_episodes(
    source: str | Path | IO[bytes] = "surveillance.rss",
    num_episodes: int = 10,  # Consider changing this into target episodes
    episode_kind: SurveillanceKind = SurveillanceKind.TK_CANDIDATE,
) -> list[Episode]:
    """Get n Episodes, filtered by a specific variant of the Surveillance podcast.

    Args:
        source: File-like object with the RSS feed, e.g., local RSS feed or open URL
        num_episodes: Number of episodes you want to scan
        episode_kind: Podcast type you want to look for
    """
    desired_episodes: list[Episode] = []

    tree = ET.parse(source)
    root = tree.getroot()

    for item in root.findall("./channel/item")[:num_episodes]:
        title = item.findtext("title", "")

        if guess_title(title) == episode_kind:
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
                    Episode(title, description, pub_date, mp3_link, transcript_url)
                )

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


def strip_episode(episode: Episode) -> str:
    """Function to strip ads from an Episode

    Args:
        episode: Episode you want to strip
    Returns:
        Filepath to the output file
    """

    opening_jingle_y, _ = librosa.load("reference/surveillance_opening_jingle.mp3")
    opening_mel = librosa.feature.melspectrogram(
        y=opening_jingle_y, sr=SAMPLE_RATE, hop_length=MEL_HOP_LENGTH
    )
    return_jingle_y, _ = librosa.load("reference/surveillance_return_jingle.mp3")
    return_mel = librosa.feature.melspectrogram(
        y=return_jingle_y, sr=SAMPLE_RATE, hop_length=MEL_HOP_LENGTH
    )

    audio_path = download_audio(
        episode.mp3, Path(f"output/dirty/episodes/{episode.title}.mp3")
    )

    cumulative_ads: int = 0
    ad_spans: list[int] = []
    end_ts: int = 0

    chunks = chunk_transcript(fetch_text(episode.transcript))
    candidates: list[int] = []

    for i, chunk in enumerate(chunks):
        ts, text = chunk
        first_26_words = " ".join(text.strip().split()[:26])

        if (
            fuzz.ratio(OPENING_TRANSCRIPT, first_26_words) > 70
            or fuzz.ratio(RETURN_TRANSCRIPT, first_26_words) > 70
        ):
            candidates.append(ts)

        if i == len(chunks) - 1:
            end_ts = ts

    logger.info(f"found {len(candidates)} candidates")

    return_timestamps: list[int] = []

    for i, ts in enumerate(candidates):
        previous_cumulative_ads = cumulative_ads
        clip_start = max(ts + cumulative_ads - 5, 0)

        logger.info(
            f"processing candidate {i}, starting clip at {int_to_ts(clip_start)}. accumulated ad time is {int_to_ts(cumulative_ads)}"
        )

        clip_audio(
            clip_start,
            180,
            str(audio_path),
            f"output/dirty/comparison/clip_{i}.wav",
        )

        clip_y, _ = librosa.load(f"output/dirty/comparison/clip_{i}.wav")
        clip_mel = librosa.feature.melspectrogram(
            y=clip_y, sr=SAMPLE_RATE, hop_length=MEL_HOP_LENGTH
        )

        return_secs: int
        confidence: float

        # if this is the opening ad read
        if i == 0:
            return_secs, confidence = find_similar_mel_ts(
                clip_mel, opening_mel, MEL_FPS
            )
        else:
            return_secs, confidence = find_similar_mel_ts(clip_mel, return_mel, MEL_FPS)

        real_ts = clip_start + return_secs

        if confidence > 0.7:
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
