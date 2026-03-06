use serde::Deserialize;
use std::collections::HashMap;
use std::path::PathBuf;

// ---------------------------------------------------------------------------
// Top-level config
// ---------------------------------------------------------------------------

#[derive(Debug, Deserialize)]
#[serde(default)]
pub struct Config {
    pub appearance: AppearanceConfig,
    pub scoring: ScoringConfig,
    pub providers: ProvidersConfig,
    pub aliases: HashMap<String, String>,
}

impl Default for Config {
    fn default() -> Self {
        Self {
            appearance: AppearanceConfig::default(),
            scoring: ScoringConfig::default(),
            providers: ProvidersConfig::default(),
            aliases: HashMap::new(),
        }
    }
}

impl Config {
    /// Load configuration from `~/.config/keystroke/config.toml`.
    ///
    /// Falls back to compiled-in defaults when the file is missing, unreadable,
    /// or contains invalid TOML.
    pub fn load() -> Self {
        let Some(path) = Self::config_path() else {
            return Self::default();
        };

        let text = match std::fs::read_to_string(&path) {
            Ok(t) => t,
            Err(_) => return Self::default(),
        };

        match toml::from_str(&text) {
            Ok(cfg) => cfg,
            Err(_) => Self::default(),
        }
    }

    /// Resolve the config file path, expanding `~` via `$HOME`.
    fn config_path() -> Option<PathBuf> {
        let home = std::env::var("HOME").ok()?;
        Some(PathBuf::from(home).join(".config/keystroke/config.toml"))
    }
}

// ---------------------------------------------------------------------------
// Appearance
// ---------------------------------------------------------------------------

#[derive(Debug, Deserialize)]
#[serde(default)]
pub struct AppearanceConfig {
    /// Maximum number of results visible in the list at once.
    pub max_visible_results: usize,
    /// Window width in pixels.
    pub width: u32,
    /// Corner radius in pixels.
    pub border_radius: u32,
}

impl Default for AppearanceConfig {
    fn default() -> Self {
        Self {
            max_visible_results: 10,
            width: 680,
            border_radius: 16,
        }
    }
}

// ---------------------------------------------------------------------------
// Scoring
// ---------------------------------------------------------------------------

#[derive(Debug, Deserialize)]
#[serde(default)]
pub struct ScoringConfig {
    /// Weight applied to the frecency bonus when combining with the fuzzy
    /// match score.  `0.0` disables frecency entirely; `1.0` would make it
    /// equal to the raw fuzzy score.
    pub frecency_weight: f64,
    /// Half-life (in days) for the frecency exponential decay.
    pub half_life_days: f64,
}

impl Default for ScoringConfig {
    fn default() -> Self {
        Self {
            frecency_weight: 0.2,
            half_life_days: 7.0,
        }
    }
}

// ---------------------------------------------------------------------------
// Providers
// ---------------------------------------------------------------------------

#[derive(Debug, Deserialize)]
#[serde(default)]
pub struct ProvidersConfig {
    /// Enable the Hyprland key-bindings provider.
    pub hyprland: bool,
}

impl Default for ProvidersConfig {
    fn default() -> Self {
        Self { hyprland: true }
    }
}
