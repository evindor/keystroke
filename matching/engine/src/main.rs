//! Keystroke Smart Match engine: a resident JSON-lines worker over local
//! Model2Vec embeddings. Requests carry stable IDs and descriptive text only;
//! replies carry IDs and similarity scores. Nothing here runs a command.
//!
//!   stdin  {"id": 1, "query": "open the browser", "rows": [{"id": "...", "text": "..."}]}
//!   stdout {"type": "result", "id": 1, "matches": [{"id": "...", "score": 0.83}]}
//!
//! `rows` replaces the catalog when present; unchanged texts keep their vectors.
//! The protocol matches helpers/matching-worker.py.

mod model;
mod tokenizer;

use std::collections::HashMap;
use std::io::{self, BufRead, Write};
use std::path::PathBuf;
use std::process;

use serde::{Deserialize, Serialize};

use model::Model;

const MAX_LINE: usize = 4 * 1024 * 1024;
const MAX_ROWS: usize = 6000;
const MAX_ID: usize = 512;
const MAX_TEXT: usize = 4096;
const MAX_QUERY: usize = 1024;
const TOP: usize = 30;

#[derive(Deserialize)]
struct Row { id: serde_json::Value, text: serde_json::Value }

#[derive(Deserialize)]
struct Request {
    id: serde_json::Value,
    #[serde(default)]
    query: serde_json::Value,
    #[serde(default)]
    rows: Option<serde_json::Value>,
}

#[derive(Serialize)]
struct Hit<'a> { id: &'a str, score: f32 }

fn emit(value: serde_json::Value) {
    let mut out = io::stdout().lock();
    let _ = serde_json::to_writer(&mut out, &value);
    let _ = out.write_all(b"\n");
    let _ = out.flush();
}

struct Index {
    model: Model,
    ids: Vec<String>,
    texts: Vec<String>,
    vectors: Vec<f32>,
    cache: HashMap<String, Vec<f32>>,
}

impl Index {
    fn new(model: Model) -> Index { Index { model, ids: Vec::new(), texts: Vec::new(), vectors: Vec::new(), cache: HashMap::new() } }

    fn update(&mut self, rows: serde_json::Value) -> Result<(), String> {
        let rows: Vec<Row> = serde_json::from_value(rows).map_err(|_| "Invalid matching catalog".to_string())?;
        if rows.len() > MAX_ROWS { return Err("Invalid matching catalog".into()); }
        let mut ids = Vec::with_capacity(rows.len());
        let mut texts = Vec::with_capacity(rows.len());
        let mut seen = std::collections::HashSet::with_capacity(rows.len());
        for row in rows {
            let (id, text) = match (row.id, row.text) {
                (serde_json::Value::String(id), serde_json::Value::String(text)) => (id, text),
                _ => return Err("Invalid matching document".into()),
            };
            if id.is_empty() || !seen.insert(id.clone()) || id.chars().count() > MAX_ID || text.chars().count() > MAX_TEXT {
                return Err("Invalid matching document size or duplicate ID".into());
            }
            ids.push(id);
            texts.push(text);
        }
        if ids == self.ids && texts == self.texts { return Ok(()); }
        let dim = self.model.dim;
        let mut next: HashMap<String, Vec<f32>> = HashMap::with_capacity(texts.len());
        let mut vectors = Vec::with_capacity(texts.len() * dim);
        for text in &texts {
            if !next.contains_key(text) {
                let vector = match self.cache.remove(text) { Some(v) => v, None => self.model.embed(text) };
                next.insert(text.clone(), vector);
            }
            vectors.extend_from_slice(&next[text]);
        }
        self.cache = next;
        self.ids = ids;
        self.texts = texts;
        self.vectors = vectors;
        Ok(())
    }

    fn query(&self, query: &serde_json::Value) -> Result<Vec<Hit<'_>>, String> {
        let text = match query { serde_json::Value::String(s) => s, _ => return Err("Invalid matching query".into()) };
        if text.chars().count() > MAX_QUERY { return Err("Invalid matching query".into()); }
        if text.trim().is_empty() || self.ids.is_empty() { return Ok(Vec::new()); }
        let vector = self.model.embed(text);
        let dim = self.model.dim;
        let mut scored: Vec<(usize, f32)> = self.vectors.chunks_exact(dim).enumerate()
            .map(|(i, row)| (i, row.iter().zip(&vector).map(|(a, b)| a * b).sum::<f32>()))
            .filter(|(_, s)| s.is_finite())
            .collect();
        scored.sort_by(|a, b| b.1.partial_cmp(&a.1).unwrap_or(std::cmp::Ordering::Equal).then(a.0.cmp(&b.0)));
        scored.truncate(TOP);
        Ok(scored.into_iter().map(|(i, score)| Hit { id: &self.ids[i], score }).collect())
    }
}

fn serve(model: Model) -> Result<(), String> {
    let mut index = Index::new(model);
    emit(serde_json::json!({"type": "ready"}));
    let stdin = io::stdin();
    let mut line = Vec::new();
    loop {
        line.clear();
        let read = stdin.lock().read_until(b'\n', &mut line).map_err(|e| e.to_string())?;
        if read == 0 { return Ok(()); }
        if line.len() > MAX_LINE { return Err("Matching request is too large".into()); }
        let request: Result<Request, _> = serde_json::from_slice(&line);
        let request = match request {
            Ok(r) if r.id.is_i64() => r,
            _ => { emit(serde_json::json!({"type": "error", "id": null, "message": "Invalid matching request"})); continue; }
        };
        let id = request.id.clone();
        let outcome = match request.rows { Some(rows) => index.update(rows), None => Ok(()) }
            .and_then(|_| index.query(&request.query).map(|hits| serde_json::to_value(hits).unwrap_or_default()));
        match outcome {
            Ok(matches) => emit(serde_json::json!({"type": "result", "id": id, "matches": matches})),
            Err(message) => emit(serde_json::json!({"type": "error", "id": id, "message": message})),
        }
    }
}

fn tokenize_stdin(model: &Model) {
    let stdin = io::stdin();
    for line in stdin.lock().lines() {
        let line = match line { Ok(l) => l, Err(_) => break };
        let text: String = serde_json::from_str(&line).unwrap_or(line);
        emit(serde_json::Value::from(model.tokenize(&text)));
    }
}

fn main() {
    let mut args = std::env::args().skip(1);
    let mut dir: Option<PathBuf> = None;
    let mut name = String::from("small");
    let mut install_only = false;
    let mut tokenize = false;
    while let Some(arg) = args.next() {
        match arg.as_str() {
            "--model-dir" => dir = args.next().map(PathBuf::from),
            "--model" => name = args.next().unwrap_or_default(),
            "--install-only" => install_only = true,
            "--tokenize" => tokenize = true,
            _ => { emit(serde_json::json!({"type": "error", "message": format!("Unknown argument {arg}")})); process::exit(2); }
        }
    }
    let dir = match dir { Some(d) => d, None => { emit(serde_json::json!({"type": "error", "message": "--model-dir is required"})); process::exit(2); } };
    let model = match Model::load(&dir) {
        Ok(m) => m,
        Err(e) => { emit(serde_json::json!({"type": "error", "message": format!("Smart Match unavailable: {e}")})); process::exit(1); }
    };
    if tokenize { tokenize_stdin(&model); return; }
    if install_only { emit(serde_json::json!({"type": "installed", "model": name})); return; }
    if let Err(e) = serve(model) {
        emit(serde_json::json!({"type": "error", "message": format!("Smart Match unavailable: {e}")}));
        process::exit(1);
    }
}
