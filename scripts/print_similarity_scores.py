import argparse
import sys
from pathlib import Path

import librosa

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from islands.analysis import cosine_similarity  # noqa: E402
from islands.audio import MEL_FPS, MEL_HOP_LENGTH, SAMPLE_RATE  # noqa: E402
from islands.text import int_to_ts, ts_to_int  # noqa: E402


def parse_timestamp(value: str) -> int:
    if ":" in value:
        return ts_to_int(value)
    return int(value)


def load_mel(path: Path, offset: int = 0, duration: int | None = None):
    y, _ = librosa.load(
        path,
        sr=SAMPLE_RATE,
        mono=True,
        offset=offset,
        duration=duration,
    )
    return librosa.feature.melspectrogram(
        y=y,
        sr=SAMPLE_RATE,
        hop_length=MEL_HOP_LENGTH,
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Print cosine similarity scores for a reference clip slid across a target clip.",
    )
    parser.add_argument(
        "reference",
        type=Path,
        help="Reference audio clip to slide across the target.",
    )
    parser.add_argument(
        "target",
        type=Path,
        help="Target audio clip or full episode to search.",
    )
    parser.add_argument(
        "--start",
        type=parse_timestamp,
        default=0,
        help="Target start offset as seconds or HH:MM:SS.",
    )
    parser.add_argument(
        "--duration",
        type=parse_timestamp,
        default=None,
        help="Target duration as seconds or HH:MM:SS. Defaults to the rest of the target.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    reference_mel = load_mel(args.reference)
    target_mel = load_mel(args.target, offset=args.start, duration=args.duration)

    print(f"reference: {args.reference}")
    print(f"target: {args.target}")
    print(f"target start: {int_to_ts(args.start)}")
    if args.duration is not None:
        print(f"target duration: {int_to_ts(args.duration)}")
    print(f"reference mel shape: {reference_mel.shape}")
    print(f"target mel shape: {target_mel.shape}")

    if reference_mel.shape[1] > target_mel.shape[1]:
        raise ValueError(
            "Reference clip is longer than the target window; cannot slide it across the target."
        )

    num_windows = target_mel.shape[1] - reference_mel.shape[1] + 1
    best_frame = 0
    best_score = float("-inf")

    print(f"num windows: {num_windows}")
    print("frame,relative_seconds,absolute_seconds,absolute_timestamp,score")

    for frame in range(num_windows):
        window = target_mel[:, frame : frame + reference_mel.shape[1]]
        score = cosine_similarity(window, reference_mel)
        relative_seconds = frame / MEL_FPS
        absolute_seconds = args.start + relative_seconds

        if score > best_score:
            best_frame = frame
            best_score = score

        print(
            f"{frame},"
            f"{relative_seconds:.3f},"
            f"{absolute_seconds:.3f},"
            f"{int_to_ts(int(absolute_seconds))},"
            f"{score:.6f}"
        )

    best_relative_seconds = best_frame / MEL_FPS
    best_absolute_seconds = args.start + best_relative_seconds

    print()
    print("best")
    print(f"  frame: {best_frame}")
    print(f"  relative_seconds: {best_relative_seconds:.3f}")
    print(f"  absolute_seconds: {best_absolute_seconds:.3f}")
    print(f"  absolute_timestamp: {int_to_ts(int(best_absolute_seconds))}")
    print(f"  score: {best_score:.6f}")


if __name__ == "__main__":
    main()
