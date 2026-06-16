import subprocess
from pathlib import Path

import librosa
import numpy as np

from .text import int_to_ts

VALID_AUDIO_SUFFIXES = {".mp3", ".wav", ".m4a", ".ogg", ".flac"}
SAMPLE_RATE = 22050
MEL_HOP_LENGTH = 512
MEL_FPS = SAMPLE_RATE / MEL_HOP_LENGTH


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
            text_references = text.strip().lower().split("\n")
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


def merge_clips(dir: str, num_cuts: int, destination: str):
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

    Path(destination).parent.mkdir(parents=True, exist_ok=True)
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
            destination,
        ],
        check=True,
    )


def get_duration(path: Path) -> str:
    """Get audio duration as a timestamp string.

    Args:
        path: path to the audio file

    Returns:
        Duration in HH:MM:SS format, truncated to whole seconds.
    """
    result = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            str(path),
        ],
        check=True,
        capture_output=True,
        text=True,
    )

    duration_seconds = int(float(result.stdout.strip()))
    return int_to_ts(duration_seconds)
