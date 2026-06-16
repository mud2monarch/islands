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
    access_key_id = os.getenv("ACCESS_KEY_ID")
    secret_access_key = os.getenv("SECRET_ACCESS_KEY")
    bucket_name = os.getenv("BUCKET_NAME")
    endpoint_url = os.getenv("BUCKET_ENDPOINT_URL")

    if (
        access_key_id is None
        or secret_access_key is None
        or bucket_name is None
        or endpoint_url is None
    ):
        raise ValueError("Missing object storage configuration")

    s3 = boto3.client(
        service_name="s3",
        endpoint_url=endpoint_url,
        aws_access_key_id=access_key_id,
        aws_secret_access_key=secret_access_key,
        region_name="auto",
    )

    key = format_bucket_key(episode)

    with open(path, "rb") as f:
        s3.upload_fileobj(f, bucket_name, key)

    logger.info(f"Uploaded {path} to {bucket_name}/{key}.")

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
    public_bucket_root = os.getenv("PUBLIC_BUCKET_ROOT")

    if public_bucket_root is None:
        raise ValueError("Missing environment variable PUBLIC_BUCKET_ROOT")

    return f"{public_bucket_root.rstrip('/')}/{key.lstrip('/')}"
