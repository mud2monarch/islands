import logging
import os
import string
import urllib.request
from pathlib import Path

import boto3
from dotenv import load_dotenv

from islands.models import Episode

logger = logging.getLogger(__name__)

load_dotenv()
ACCESS_KEY_ID = os.getenv("ACCESS_KEY_ID")
SECRET_ACCESS_KEY = os.getenv("SECRET_ACCESS_KEY")
BUCKET_NAME = os.getenv("BUCKET_NAME")
ENDPOINT_URL = os.getenv("BUCKET_ENDPOINT_URL")
PUBLIC_BUCKET_ROOT = os.getenv("PUBLIC_BUCKET_ROOT")


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


def upload_episode(path: Path, episode: Episode) -> str:
    """Uploads an episode to object storage and returns the key

    Args:
        path: Path to the episode file
        episode: Episode object

    Returns:
        The key of the uploaded episode
    """

    if (
        ACCESS_KEY_ID is None
        or SECRET_ACCESS_KEY is None
        or BUCKET_NAME is None
        or ENDPOINT_URL is None
    ):
        raise ValueError("Missing object storage configuration")

    s3 = boto3.client(
        service_name="s3",
        endpoint_url=ENDPOINT_URL,
        aws_access_key_id=ACCESS_KEY_ID,
        aws_secret_access_key=SECRET_ACCESS_KEY,
        region_name="auto",
    )

    key = format_bucket_key(episode)

    with open(path, "rb") as f:
        s3.upload_fileobj(
            f,
            BUCKET_NAME,
            key,
            ExtraArgs={"ContentType": "audio/mpeg"},
        )

    logger.info(f"Uploaded {path} to {BUCKET_NAME}/{key}.")

    return key


def format_bucket_key(episode: Episode) -> str:
    """Trivial helper function to normalize episodes to object storage keys

    args:
        episode: the Episode you want
    returns:
        Normalized r2 key for the episode in form `podcast-title/guid.mp3`
    """
    podcast_title = normalize_key_part(episode.podcast.title)
    guid = normalize_key_part(episode.guid)

    return f"{podcast_title}/{guid}.mp3"


def normalize_key_part(text: str) -> str:
    """Trivial helper function to normalize titles or guids

    args:
        text: the text to normalize
    returns:
        Normalized text: no punctuation, lowercase, spaces replaced by hyphens
    """
    no_punct = text.translate(str.maketrans("", "", string.punctuation)).lower()

    return "-".join(no_punct.split())


def get_public_object_url(key: str) -> str:

    if PUBLIC_BUCKET_ROOT is None:
        raise ValueError("Missing environment variable PUBLIC_BUCKET_ROOT")

    return f"{PUBLIC_BUCKET_ROOT.rstrip('/')}/{key.lstrip('/')}"


def upload_rss_feed(path: Path, prefix: str | None = None) -> str:
    """Upload rss feed to object storage"""

    if (
        ACCESS_KEY_ID is None
        or SECRET_ACCESS_KEY is None
        or BUCKET_NAME is None
        or ENDPOINT_URL is None
    ):
        raise ValueError("Missing object storage configuration")

    s3 = boto3.client(
        service_name="s3",
        endpoint_url=ENDPOINT_URL,
        aws_access_key_id=ACCESS_KEY_ID,
        aws_secret_access_key=SECRET_ACCESS_KEY,
        region_name="auto",
    )

    # output/clean/{normalize_title(podcast.title)}.xml
    if prefix is not None:
        key = f"{prefix}-{str(path).split('/')[-1]}"
    else:
        key = str(path).split("/")[-1]

    with open(path, "rb") as f:
        s3.upload_fileobj(
            f,
            BUCKET_NAME,
            key,
            ExtraArgs={"ContentType": "application/rss+xml; charset=utf-8"},
        )

    logger.info(f"Uploaded {path} to {BUCKET_NAME}/{key}.")

    return key
