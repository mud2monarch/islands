import logging
import subprocess
import urllib.request
import xml.etree.ElementTree as ET
from enum import Enum
from pathlib import Path

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
    TK = "tk"
    TK_IDEA = "tk_idea"
    MONEY = "money"


class MediaKind(Enum):
    AUDIO = "audio/mpeg"
    JPEG = "image/jpeg"


class TranscriptKind(Enum):
    VTT = "text/vtt"
    SRT = "application/srt"
    TEXT = "text/plain"


def parse_title(title: str) -> SurveillanceKind:
    if "Bloomberg Surveillance TV" in title:
        return SurveillanceKind.FERRO

    if "Single Best Idea" in title or "Tom Keene" in title:
        return SurveillanceKind.TK_IDEA

    if "Bloomberg Money" in title:
        return SurveillanceKind.MONEY

    return SurveillanceKind.TK


def filter_n_episodes(
    feed: str = "surveillance.rss",
    num_episodes: int = 10,
    episode_kind: SurveillanceKind = SurveillanceKind.TK,
) -> list[Episode]:
    desired_episodes: list[Episode] = []

    tree = ET.parse(feed)
    root = tree.getroot()

    for item in root.findall("./channel/item")[:num_episodes]:
        title = item.findtext("title", "")

        if parse_title(title) == episode_kind:
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
    try:
        h, m, s = text_ts.split(":")
        return int(h) * 3600 + int(m) * 60 + int(s)
    except ValueError as exc:
        raise ValueError(f"Invalid timestamp: {text_ts!r}") from exc


def int_to_ts(seconds: int) -> str:
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
    chunks = []
    blocks = transcript.strip().lower().split("\n\n")

    for block in blocks:
        ts, text = block.strip().split("\n")
        chunks.append((ts_to_int(ts), text))

    return chunks


def download_audio(url: str, output_path: Path) -> Path:
    logger.info(f"Downloading audio from {url} to {output_path}.")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    urllib.request.urlretrieve(url, output_path)
    return output_path


"""
Fetch transcript into memory
"""


def fetch_transcript(url: str) -> str:
    with urllib.request.urlopen(url) as response:
        return response.read().decode("utf-8")


def strip_episode(episode: Episode) -> str:

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

    chunks = chunk_transcript(fetch_transcript(episode.transcript))
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
