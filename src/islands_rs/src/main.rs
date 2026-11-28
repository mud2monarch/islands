use anyhow::{Context, Error};
use base64::Engine;
use reqwest::Client;
use serde::Deserialize;
use serde_json::{Value, json};
use std::fmt::Write;
use std::process::Command;
use std::{env, path::Path};

#[tokio::main]
async fn main() -> Result<(), Error> {
    dotenvy::dotenv().ok();
    const MODEL: &str = "google/gemini-3.8-flash";
    const EFFORT: &str = "high";
    const RESPONSES_API: &str = "https://openrouter.ai/api/v1/responses";
    const AUDIO_PATH: &str =
        "/Users/zach.wong/Downloads/Bloomberg_Surveillance_TV_November_25th_2026.mp3";

    let llm_prompt: String = std::fs::read_to_string("islands_llm_prompt.txt")
        .expect("You must include an llm prompt for Islands.");

    let openrouter_api_key: String =
        env::var("OPENROUTER_API_KEY").expect("Openrouter API key not set in .env file.");

    let audio_b64 = encode_audio_to_base64(Path::new(AUDIO_PATH))?;

    let input_items = json!({
            "role": "user",
            "content": [
                {"type": "input_text", "text": llm_prompt},
                {
                    "type": "input_audio",
                    "input_audio": {"data": audio_b64, "format": "mp3"},
                },
            ]
    });

    let islands_schema: Value = serde_json::from_str(include_str!("islands_llm_schema.json"))?;

    let payload = json!({
        "model": MODEL,
        "reasoning": {
            "effort": EFFORT,
        },
        "input": [input_items],
        "text": islands_schema
    });

    let client = Client::builder().build()?;

    let response = client
        .post(RESPONSES_API)
        .bearer_auth(&openrouter_api_key)
        .json(&payload)
        .send()
        .await?;

    let full: OpenrouterFullResponse = response.json().await?;

    let part: &OpenrouterMessageContent = full
        .output
        .iter()
        .find(|m| m.r#type == "message" && m.role.as_deref() == Some("assistant"))
        .and_then(|m| m.content.as_deref())
        .and_then(|m| m.iter().find(|p| p.r#type == "output_text"))
        .context("Response did not include an assistant message with output text.")?;

    let islands: SetOfContentChunks = serde_json::from_str(&part.text)?;

    println!("{:?}", islands);

    // Why does this need to be mutable?
    let mut command = get_ffmpeg_command_from_chunks(AUDIO_PATH, &islands.content_chunks, None)?;

    let status = command.status()?;
    anyhow::ensure!(status.success(), "ffmpeg exited with {status}");

    Ok(())
}

fn encode_audio_to_base64(path: &Path) -> Result<String, Error> {
    let file: Vec<u8> = std::fs::read(path)?;
    Ok(base64::engine::general_purpose::STANDARD.encode(&file))
}

fn get_ffmpeg_command_from_chunks(
    podcast_location: &str,
    chunks: &[ContentChunk],
    output_dir: Option<&Path>,
) -> Result<Command, Error> {
    let output_dir = output_dir.unwrap_or(Path::new("outputs/clean/"));

    // We need to produce an ffmpeg argument for `-filter_complex` in the following form
    // (as an example splitting then joining three segments):
    //
    // [0:a:0]asplit=3[a0][a1][a2];
    // [a0]atrim=start=72:end=504,asetpts=PTS-STARTPTS[c0];
    // [a1]atrim=start=609:end=1038,asetpts=PTS-STARTPTS[c1];
    // [a2]atrim=start=1179:end=1546,asetpts=PTS-STARTPTS[c2];
    // [c0][c1][c2]concat=n=3:v=0:a=1[out]
    let num_chunks = chunks.len();

    let mut filter_graph = format!("[0:a:0]asplit={num_chunks}");

    for i in 0..num_chunks {
        write!(filter_graph, "[a{i}]").unwrap();
    }
    write!(filter_graph, ";").unwrap();
    for i in 0..num_chunks {
        write!(
            filter_graph,
            "[a{i}]atrim=start={}:end={},asetpts=PTS-STARTPTS[c{i}];",
            chunks[i].start_seconds, chunks[i].end_seconds
        )
        .expect(
            "writing to string should succeed; indices of chunks all between 0..chunks.len(), range exclusive",
        );
    }
    for i in 0..num_chunks {
        write!(filter_graph, "[c{i}]").unwrap();
    }
    write!(filter_graph, "concat=n={num_chunks}:v=0:a=1[out]").unwrap();

    // println!("{}", filter_graph);

    std::fs::create_dir_all(output_dir)?;

    let mut command = Command::new("ffmpeg");
    command.args([
        "-i",
        podcast_location,
        "-filter_complex",
        &filter_graph,
        "-map",
        "[out]",
    ]);
    command.arg(output_dir.join("edited-podcast.mp3"));

    Ok(command)
}

#[derive(Deserialize, Debug)]
pub struct OpenrouterFullResponse {
    pub output: Vec<OpenrouterMessage>,
}

#[derive(Deserialize, Debug)]
pub struct OpenrouterMessage {
    pub r#type: String,
    pub role: Option<String>,
    pub content: Option<Vec<OpenrouterMessageContent>>,
}

#[derive(Deserialize, Debug)]
pub struct OpenrouterMessageContent {
    pub r#type: String,
    pub text: String,
}

#[derive(Deserialize, Debug)]
pub struct SetOfContentChunks {
    pub content_chunks: Vec<ContentChunk>,
}

#[derive(Deserialize, Debug)]
pub struct ContentChunk {
    pub start_seconds: usize,
    pub end_seconds: usize,
}
