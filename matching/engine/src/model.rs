//! A Model2Vec static model: one F32 embedding row per vocabulary entry read
//! from `model.safetensors`, mean-pooled over the token ids of a text.

use std::fs;
use std::path::Path;

use crate::tokenizer::Tokenizer;

pub struct Model {
    tokenizer: Tokenizer,
    embeddings: Vec<f32>,
    rows: usize,
    pub dim: usize,
}

fn read_safetensors(path: &Path) -> Result<(Vec<f32>, usize, usize), String> {
    let bytes = fs::read(path).map_err(|e| format!("{}: {e}", path.display()))?;
    if bytes.len() < 8 { return Err("model.safetensors: truncated header".into()); }
    let header_len = u64::from_le_bytes(bytes[..8].try_into().unwrap()) as usize;
    if header_len > 1 << 20 || 8 + header_len > bytes.len() { return Err("model.safetensors: bad header length".into()); }
    let header: serde_json::Value = serde_json::from_slice(&bytes[8..8 + header_len]).map_err(|e| format!("model.safetensors header: {e}"))?;
    let tensor = header.get("embeddings").ok_or("model.safetensors: no embeddings tensor")?;
    if tensor["dtype"] != "F32" { return Err("model.safetensors: embeddings must be F32".into()); }
    let shape = tensor["shape"].as_array().ok_or("model.safetensors: bad shape")?;
    if shape.len() != 2 { return Err("model.safetensors: embeddings must be two-dimensional".into()); }
    let rows = shape[0].as_u64().unwrap_or(0) as usize;
    let dim = shape[1].as_u64().unwrap_or(0) as usize;
    let offsets = tensor["data_offsets"].as_array().ok_or("model.safetensors: bad offsets")?;
    let start = 8 + header_len + offsets[0].as_u64().unwrap_or(0) as usize;
    let end = 8 + header_len + offsets[1].as_u64().unwrap_or(0) as usize;
    if end > bytes.len() || end - start != rows * dim * 4 { return Err("model.safetensors: tensor size mismatch".into()); }
    let data = bytes[start..end].chunks_exact(4).map(|c| f32::from_le_bytes([c[0], c[1], c[2], c[3]])).collect();
    Ok((data, rows, dim))
}

impl Model {
    pub fn load(dir: &Path) -> Result<Model, String> {
        let config: serde_json::Value = serde_json::from_str(&fs::read_to_string(dir.join("config.json")).map_err(|e| format!("config.json: {e}"))?)
            .map_err(|e| format!("config.json: {e}"))?;
        if config["model_type"] != "model2vec" { return Err("config.json: not a model2vec model".into()); }
        let tokenizer = Tokenizer::from_json(&fs::read_to_string(dir.join("tokenizer.json")).map_err(|e| format!("tokenizer.json: {e}"))?)?;
        let (embeddings, rows, dim) = read_safetensors(&dir.join("model.safetensors"))?;
        if rows == 0 || dim == 0 { return Err("model.safetensors: empty embeddings".into()); }
        Ok(Model { tokenizer, embeddings, rows, dim })
    }

    pub fn tokenize(&self, text: &str) -> Vec<u32> {
        let unk = self.tokenizer.unk_id();
        self.tokenizer.encode(text).into_iter().filter(|&id| id != unk).collect()
    }

    /// Mean of the token vectors, L2-normalized; all zeros for a text without
    /// known tokens (which then scores 0 against everything).
    pub fn embed(&self, text: &str) -> Vec<f32> {
        let mut out = vec![0f32; self.dim];
        let ids = self.tokenize(text);
        let mut count = 0usize;
        for id in ids {
            let id = id as usize;
            if id >= self.rows { continue; }
            let row = &self.embeddings[id * self.dim..(id + 1) * self.dim];
            for (o, v) in out.iter_mut().zip(row) { *o += v; }
            count += 1;
        }
        if count == 0 { return out; }
        let scale = 1.0 / count as f32;
        for o in out.iter_mut() { *o *= scale; }
        let norm = out.iter().map(|v| v * v).sum::<f32>().sqrt();
        if norm > 1e-12 { for o in out.iter_mut() { *o /= norm; } }
        out
    }
}
