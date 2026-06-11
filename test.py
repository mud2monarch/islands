import re
import subprocess
from pathlib import Path

from readwrite import int_to_ts

CUTS_DIR = Path("output/dirty/cuts")


def cut_index(path: Path) -> int:
    match = re.fullmatch(r"cut_(\d+)\.wav", path.name)
    if match is None:
        raise ValueError(f"Unexpected cut filename: {path.name}")

    return int(match.group(1))


def audio_duration(path: Path) -> float:
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

    return float(result.stdout.strip())


for cut in sorted(CUTS_DIR.glob("cut_*.wav"), key=cut_index):
    duration = audio_duration(cut)
    print(f"{cut.name}: {int_to_ts(round(duration))} ({duration:.2f}s)")
