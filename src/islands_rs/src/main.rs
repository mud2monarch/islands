use anyhow::{Context, Error};
use base64::Engine;
use reqwest::{
    Client,
    header::{AUTHORIZATION, CONTENT_TYPE, HeaderMap, HeaderValue},
};
use serde::Deserialize;
use serde_json::{Value, json};
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

    let openrouter_api_key: String =
        env::var("OPENROUTER_API_KEY").expect("Openrouter API key not set in .env file.");

    let llm_prompt: String = std::fs::read_to_string("islands_llm_prompt.txt")
        .expect("You must include an llm prompt for Islands.");

    let audio_b64 = encode_audio_to_base64(Path::new(AUDIO_PATH))?;

    let mut headers = HeaderMap::new();
    headers.insert(
        AUTHORIZATION,
        HeaderValue::from_str(&format!("Bearer {}", openrouter_api_key)).unwrap(),
    );
    headers.insert(CONTENT_TYPE, "application/json".parse().unwrap());

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

    let text: Value = serde_json::from_str(include_str!("islands_llm_schema.json"))?;

    let payload = json!({
        "model": MODEL,
        "reasoning": {
            "effort": EFFORT,
        },
        "input": [input_items],
        "text": text
    });

    let client = Client::builder().build()?;

    let response = client
        .post(RESPONSES_API)
        .bearer_auth(&openrouter_api_key)
        .json(&payload)
        .send()
        .await?;

    let full: OpenrouterFullResponse = response.json().await?;

    let part = full
        .output
        .iter()
        .find(|m| m.r#type == "message" && m.role.as_deref() == Some("assistant"))
        .and_then(|m| m.content.as_deref())
        .and_then(|m| m.iter().find(|p| p.r#type == "output_text"))
        .context("Response did not include an assistant message with output text.")?;

    let islands: SetOfContentChunks = serde_json::from_str(&part.text)?;

    let println!("{:?}", islands);

    Ok(())
}

fn encode_audio_to_base64(path: &Path) -> Result<String, Error> {
    let file: Vec<u8> = std::fs::read(path)?;
    Ok(base64::engine::general_purpose::STANDARD.encode(&file))
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
