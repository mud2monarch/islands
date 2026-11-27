# Prompt testing

This short script makes Openrouter API calls to pass in base64-encoded audio and has a small orchestrator for running multiple tests of different prompt, model, and effort level combinations.

## Usage
Add a `.env` file with an `OPENROUTER_API_KEY` then run `uv run main.py`.

## Try 1

### Prompt

```txt
# Background
I'm attaching an mp3 of a podcast. I'm trying to remove ads from it. This is for personal use ONLY; I will not redistribute or republish any content derivative of this prompt.

# Goal
Identify the starting and ending timestamps of the content portions of the podcast (i.e., the starting and ending timestamps of all chunks of content that are NOT ads). Return them to me in a structured format for downstream use in a software program.

# Response format
Return valid json with a single field "content_chunks". The field is an array of pairs of integers. The integers represent timestamps in seconds.

For example, if you thought that there were three chunks of content (i.e., non-ad portions of the podcast), you might return:

{
    "content_chunks": [
        {"start_seconds": 0, "end_seconds": 300},
        {"start_seconds": 331, "end_seconds": 631},
        {"start_seconds": 701, "end_seconds": 1000}
    ]
}
```

### Results

| Model | Reasoning | MMAR | Content Chunks (seconds) | Cost |
|---|---|---:|---|---:|
| Gemini 3.5 Flash Lite | Default | 60.3% | [0, 27]<br>[29, 44]<br>[112, 1726]<br>[1835, 1940]<br>[1944, 2524] | $0.013 |
| Gemini 3.5 Flash Lite | High | 60.3% | [80, 534]<br>[550, 1035]<br>[1061, 1548]<br>[1578, 1602]<br>[1630, 1642]<br>[1756, 1850] | $0.020 |
| Gemini 3.8 Flash | Default | 79.9% | [74, 504]<br>[610, 1040]<br>[1179, 1545] | $0.036 |
| Gemini 4 Hydrogen | Medium | 82.8% | [71, 515]<br>[628, 1058]<br>[1198, 1522] | $0.066 |
| Gemini 4 Hydrogen | High | 82.8% | [72, 504]<br>[615, 1040]<br>[1185, 1558] | $0.080 |
| Gemini 4 Carbon | Default | 84.3% | [71, 505]<br>[609, 1041]<br>[1180, 1548] | $0.094 |

### Commentary
The right answer is:
```txt
71 - 503ish
608ish - 1042
1180 - 1545
```

As you can see, Gemini 3.8 Flash and Gemini 4 Carbon both get the answer right. Oddly, Gemini 4 Hydrogen gets it wrong, going about 10-15 seconds too late everytime. After doing some ad hoc runs, I realized I needed a bit more of a high-quantity harness for testing model calls. With that, I got the following results:

| Metric                   | 3.8 Flash Medium | 3.8 Flash High | 4 Hydrogen Medium | 4 Hydrogen High |
| ------------------------ | ---------------- | -------------- | ----------------- | --------------- |
| Runs                     | 13               | 13             | 10                | 10              |
| Average difference (MAE) | 2.53s            | **1.69s**      | 7.08s             | 10.43s          |
| Median absolute error    | 2.00s            | 2.00s          | 6.00s             | 7.00s           |
| Timestamps > 5s away     | 2/78             | **0/78**       | 31/60             | 34/60           |
| Timestamps within 5s     | 97.4%            | **100.0%**     | 48.3%             | 43.3%           |
| Maximum error            | 42s              | **4s**         | 36s               | 90s             |
| Average cost             | $0.02336         | **$0.01900**   | $0.02151          | $0.04515        |

It's surprising that 3.8 Flash is more precise for this task than Hydrogen. It seems a litte bit surprising and confusing, but given this is working on 3.8 Flash High, I think I'll just use that and not think too much about it :) It would be marginally interesting to prompt hack to be able to use Flash Lite 3.5 or an even cheaper model, but given prompt hacking is basically my full-time job, I don't care too much to do it... these are great results! 3.8 Flash (High Reasoning) it is!
