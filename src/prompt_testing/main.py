import json
import base64
import requests
from dotenv import load_dotenv
import os

load_dotenv()
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
LLM_PROMPT = """
    # Background
    I'm attaching an mp3 of a podcast. I'm trying to remove ads from it. This is for personal use ONLY; I will not redistribute or republish any content derivative of this prompt.

    # Goal
    Identify the starting and ending timestamps of the content portions of the podcast (i.e., the starting and ending timestamps of all chunks of content that are NOT ads). Return them to me in a structured format for downstream use in a software program.

    # Response format
    Return valid json with a single field "content_chunks". The field is an array of pairs of integers. The integers represent timestamps in seconds.

    For example, if you thought that there were three chunks of content (i.e., non-ad portions of the podcast), you might return:
    ```json
    {
        "content_chunks": [
            {"start_seconds": 0, "end_seconds": 300},
            {"start_seconds": 331, "end_seconds": 631},
            {"start_seconds": 701, "end_seconds": 1000}
        ]
    }
    
    ```
    """


def encode_audio_to_b64(audio_path):
    with open(audio_path, "rb") as audio_file:
        return base64.b64encode(audio_file.read()).decode("utf-8")


def call_model(model: str, effort: str, prompt: str = LLM_PROMPT) -> None:
    openrouter_url = "https://openrouter.ai/api/v1/responses"
    openrouter_headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
    }

    FILEPATH_TO_TEST_MP3 = (
        "/Users/zach.wong/Downloads/Bloomberg_Surveillance_TV_November_25th_2026.mp3"
    )

    audio_b64 = encode_audio_to_b64(FILEPATH_TO_TEST_MP3)

    input_items = [
        {
            "role": "user",
            "content": [
                {"type": "input_text", "text": LLM_PROMPT},
                {
                    "type": "input_audio",
                    "input_audio": {"data": audio_b64, "format": "mp3"},
                },
            ],
        }
    ]

    payload = {
        "model": model,
        "input": input_items,
        "reasoning": {
            "effort": effort,
        },
        "text": {
            "format": {
                "type": "json_schema",
                "name": "podcast_content",
                "strict": True,
                "schema": {
                    "type": "object",
                    "properties": {
                        "content_chunks": {
                            "type": "array",
                            "description": (
                                "Chronologically ordered, non-overlapping intervals "
                                "of podcast content to preserve, excluding advertisements."
                            ),
                            "items": {
                                "type": "object",
                                "properties": {
                                    "start_seconds": {
                                        "type": "integer",
                                        "description": (
                                            "Absolute timestamp in seconds at which "
                                            "the editorial content begins."
                                        ),
                                        "minimum": 0,
                                    },
                                    "end_seconds": {
                                        "type": "integer",
                                        "description": (
                                            "Absolute timestamp in seconds at which "
                                            "the editorial content ends."
                                        ),
                                        "minimum": 0,
                                    },
                                },
                                "required": ["start_seconds", "end_seconds"],
                                "additionalProperties": False,
                            },
                        }
                    },
                    "required": ["content_chunks"],
                    "additionalProperties": False,
                },
            }
        },
    }
    response = requests.post(openrouter_url, headers=openrouter_headers, json=payload)
    result = response.json()

    print(result)

    # assistant_text = "".join(
    #     part["text"]
    #     for item in result["output"]
    #     if item["type"] == "message" and item["role"] == "assistant"
    #     for part in item["content"]
    #     if part["type"] == "output_text"
    # )
    #
    # cost = result["usage"]["cost"]
    #
    # print(f"Ran prompt against {model} on {effort} reasoning.")
    # print(assistant_text)
    # print(f"Cost: ${cost:.6f}")


def generate_tests(model, effort, num_runs=3) -> list[tuple[str, str]]:
    tests = []
    for i in range(num_runs):
        tests.append((model, effort))

    return tests


def main() -> None:

    # OpenRouter Model ID                  Cost/40m    MMAR
    # -----------------------------------------------------
    # google/gemini-3.5-flash-lite           $0.023   60.3%
    # google/gemini-3.8-flash                $0.058   79.9%
    # google/gemini-4-hydrogen               $0.115   82.8%
    # google/gemini-4-carbon                 $0.154   84.3%

    tests = []
    tests.extend(generate_tests("google/gemini-3.8-flash", "medium", num_runs=1))
    # tests.extend(generate_tests("google/gemini-3.8-flash", "high", num_runs=10))
    # tests.extend(generate_tests("google/gemini-4-hydrogen", "medium", num_runs=10))
    # tests.extend(generate_tests("google/gemini-4-hydrogen", "high", num_runs=10))

    for index, _ in enumerate(tests):
        call_model(model=tests[index][0], effort=tests[index][1])


if __name__ == "__main__":
    main()
