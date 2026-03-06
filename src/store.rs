use serde::{Deserialize, Serialize};
use std::collections::HashMap;
use std::fs;
use std::path::PathBuf;
use std::time::SystemTime;

/// A single frecency entry: a raw score anchored at a reference time.
///
/// The *effective* (decayed) score at time `now` is:
///
///     score / 2^((now - ref_time) / half_life)
///
/// This is the exponential-decay model used by `fre`.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Entry {
    pub score: f64,
    pub ref_time: u64,
}

/// On-disk JSON layout.
#[derive(Debug, Clone, Serialize, Deserialize)]
struct StoreData {
    version: u32,
    global: HashMap<String, Entry>,
    queries: HashMap<String, HashMap<String, Entry>>,
}

impl StoreData {
    fn empty() -> Self {
        Self {
            version: 1,
            global: HashMap::new(),
            queries: HashMap::new(),
        }
    }
}

/// Frecency store with two levels of tracking (global and per-query).
///
/// # Half-life
///
/// The `half_life` parameter (in seconds) controls how quickly scores decay.
/// After `half_life` seconds of inactivity an entry's effective score is halved.
/// The default is 604800 s (7 days).
pub struct Store {
    data: StoreData,
    half_life: f64,
    path: PathBuf,
}

impl Store {
    // --------------------------------------------------------------------
    // Construction
    // --------------------------------------------------------------------

    /// Load the store from `~/.local/share/keystroke/history.json`, or create
    /// an empty one if the file does not exist or is corrupt.
    ///
    /// `half_life_secs` controls the exponential-decay half-life (seconds).
    /// A sensible default is `604800.0` (one week).
    pub fn load(half_life_secs: f64) -> Self {
        let path = Self::store_path();
        let data = Self::read_data(&path);
        Self {
            data,
            half_life: half_life_secs,
            path,
        }
    }

    // --------------------------------------------------------------------
    // Recording
    // --------------------------------------------------------------------

    /// Record a selection: bump both the global and per-query frecency for
    /// `command_id`.  The query is normalized (lowercased, trimmed) before
    /// storage.
    pub fn record(&mut self, query: &str, command_id: &str) {
        let now = Self::now();

        // Global entry
        Self::bump_entry(
            self.data.global.entry(command_id.to_owned()).or_insert(Entry {
                score: 0.0,
                ref_time: now,
            }),
            now,
            self.half_life,
        );

        // Per-query entry (only if the query is non-empty after normalization)
        let nq = Self::normalize(query);
        if !nq.is_empty() {
            let query_map = self
                .data
                .queries
                .entry(nq)
                .or_insert_with(HashMap::new);
            Self::bump_entry(
                query_map.entry(command_id.to_owned()).or_insert(Entry {
                    score: 0.0,
                    ref_time: now,
                }),
                now,
                self.half_life,
            );
        }
    }

    // --------------------------------------------------------------------
    // Querying
    // --------------------------------------------------------------------

    /// Return the decayed global score for `command_id` (0.0 if unknown).
    pub fn global_score(&self, command_id: &str) -> f64 {
        self.data
            .global
            .get(command_id)
            .map_or(0.0, |e| Self::decayed_score(e, Self::now(), self.half_life))
    }

    /// Return the decayed per-query score for `(query, command_id)` (0.0 if
    /// unknown).  The query is normalized before lookup.
    pub fn query_score(&self, query: &str, command_id: &str) -> f64 {
        let nq = Self::normalize(query);
        self.data
            .queries
            .get(&nq)
            .and_then(|m| m.get(command_id))
            .map_or(0.0, |e| Self::decayed_score(e, Self::now(), self.half_life))
    }

    /// Return the top `n` command IDs ordered by decayed global score
    /// (descending).  Useful for the empty-query / initial state.
    pub fn top_global(&self, n: usize) -> Vec<(String, f64)> {
        let now = Self::now();
        let mut scored: Vec<(String, f64)> = self
            .data
            .global
            .iter()
            .map(|(id, e)| (id.clone(), Self::decayed_score(e, now, self.half_life)))
            .collect();
        // Sort descending by score, then alphabetically for stability.
        scored.sort_by(|a, b| {
            b.1.partial_cmp(&a.1)
                .unwrap_or(std::cmp::Ordering::Equal)
                .then_with(|| a.0.cmp(&b.0))
        });
        scored.truncate(n);
        scored
    }

    // --------------------------------------------------------------------
    // Persistence
    // --------------------------------------------------------------------

    /// Persist the store to disk (creates parent directories if needed).
    pub fn save(&self) {
        if let Some(parent) = self.path.parent() {
            if let Err(e) = fs::create_dir_all(parent) {
                eprintln!("keystroke: failed to create store directory: {e}");
                return;
            }
        }
        match serde_json::to_string_pretty(&self.data) {
            Ok(json) => {
                if let Err(e) = fs::write(&self.path, json) {
                    eprintln!("keystroke: failed to write {}: {e}", self.path.display());
                }
            }
            Err(e) => {
                eprintln!("keystroke: failed to serialize store: {e}");
            }
        }
    }

    // --------------------------------------------------------------------
    // Internal helpers
    // --------------------------------------------------------------------

    /// Resolve `~/.local/share/keystroke/history.json`.
    fn store_path() -> PathBuf {
        let home = std::env::var("HOME").unwrap_or_else(|_| "/tmp".to_owned());
        PathBuf::from(home)
            .join(".local")
            .join("share")
            .join("keystroke")
            .join("history.json")
    }

    /// Try to read and deserialize the store data; fall back to an empty store.
    fn read_data(path: &PathBuf) -> StoreData {
        match fs::read_to_string(path) {
            Ok(contents) => serde_json::from_str(&contents).unwrap_or_else(|e| {
                eprintln!(
                    "keystroke: corrupt history file ({}), starting fresh: {e}",
                    path.display()
                );
                StoreData::empty()
            }),
            Err(_) => StoreData::empty(),
        }
    }

    /// Current Unix epoch time in seconds.
    fn now() -> u64 {
        SystemTime::now()
            .duration_since(SystemTime::UNIX_EPOCH)
            .map(|d| d.as_secs())
            .unwrap_or(0)
    }

    /// Compute the decayed score: `entry.score / 2^((now - ref_time) / half_life)`.
    fn decayed_score(entry: &Entry, now: u64, half_life: f64) -> f64 {
        let elapsed = now.saturating_sub(entry.ref_time) as f64;
        entry.score / (2.0_f64).powf(elapsed / half_life)
    }

    /// Bump an entry: decay the stored score to the current moment, add 1.0,
    /// and set `ref_time` to `now`.
    fn bump_entry(entry: &mut Entry, now: u64, half_life: f64) {
        let current = Self::decayed_score(entry, now, half_life);
        entry.score = current + 1.0;
        entry.ref_time = now;
    }

    /// Normalize a query string: trim whitespace and lowercase.
    fn normalize(query: &str) -> String {
        query.trim().to_lowercase()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    /// Build a store that won't touch disk.
    fn test_store(half_life: f64) -> Store {
        Store {
            data: StoreData::empty(),
            half_life,
            path: PathBuf::from("/dev/null"),
        }
    }

    #[test]
    fn empty_scores_are_zero() {
        let s = test_store(604800.0);
        assert_eq!(s.global_score("foo"), 0.0);
        assert_eq!(s.query_score("bar", "foo"), 0.0);
    }

    #[test]
    fn record_bumps_both_levels() {
        let mut s = test_store(604800.0);
        s.record("vs", "hyprland:togglesplit");

        assert!(s.global_score("hyprland:togglesplit") > 0.9);
        assert!(s.query_score("vs", "hyprland:togglesplit") > 0.9);
        // Unrelated query is still zero
        assert_eq!(s.query_score("other", "hyprland:togglesplit"), 0.0);
    }

    #[test]
    fn multiple_records_accumulate() {
        let mut s = test_store(604800.0);
        s.record("q", "cmd");
        s.record("q", "cmd");
        s.record("q", "cmd");

        // Three immediate bumps: ~3.0 (negligible decay within a test)
        let score = s.global_score("cmd");
        assert!(score > 2.9 && score < 3.1, "score was {score}");
    }

    #[test]
    fn decay_halves_after_half_life() {
        let half_life = 100.0;
        let mut entry = Entry {
            score: 4.0,
            ref_time: 1000,
        };
        // Simulate "now" being 100s later
        let decayed = Store::decayed_score(&entry, 1100, half_life);
        assert!(
            (decayed - 2.0).abs() < 0.001,
            "expected ~2.0, got {decayed}"
        );

        // Bump at t=1100
        Store::bump_entry(&mut entry, 1100, half_life);
        assert!((entry.score - 3.0).abs() < 0.001);
        assert_eq!(entry.ref_time, 1100);
    }

    #[test]
    fn normalize_trims_and_lowercases() {
        assert_eq!(Store::normalize("  Hello World  "), "hello world");
        assert_eq!(Store::normalize("VS"), "vs");
    }

    #[test]
    fn top_global_ordering() {
        let mut s = test_store(604800.0);
        s.record("a", "alpha");
        s.record("b", "beta");
        s.record("b", "beta");
        s.record("c", "gamma");
        s.record("c", "gamma");
        s.record("c", "gamma");

        let top = s.top_global(2);
        assert_eq!(top.len(), 2);
        assert_eq!(top[0].0, "gamma");
        assert_eq!(top[1].0, "beta");
    }

    #[test]
    fn empty_query_does_not_create_per_query_entry() {
        let mut s = test_store(604800.0);
        s.record("", "cmd");
        s.record("   ", "cmd");
        assert!(s.data.queries.is_empty());
        // Global should still be tracked
        assert!(s.global_score("cmd") > 1.5);
    }

    #[test]
    fn serialization_roundtrip() {
        let mut data = StoreData::empty();
        data.global.insert(
            "hyprland:killactive".into(),
            Entry {
                score: 15.0,
                ref_time: 1709740800,
            },
        );
        let mut inner = HashMap::new();
        inner.insert(
            "hyprland:togglesplit".into(),
            Entry {
                score: 42.0,
                ref_time: 1709740800,
            },
        );
        data.queries.insert("vs".into(), inner);

        let json = serde_json::to_string_pretty(&data).unwrap();
        let parsed: StoreData = serde_json::from_str(&json).unwrap();

        assert_eq!(parsed.version, 1);
        assert_eq!(parsed.global["hyprland:killactive"].score, 15.0);
        assert_eq!(
            parsed.queries["vs"]["hyprland:togglesplit"].ref_time,
            1709740800
        );
    }
}
