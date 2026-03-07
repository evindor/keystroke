use serde::Deserialize;
use std::collections::{HashMap, HashSet};
use std::path::PathBuf;

/// Embedded default catalog, written to data dir on first run.
const DEFAULT_CATALOG: &str = include_str!("catalog.toml");

// ---------------------------------------------------------------------------
// Catalog entry
// ---------------------------------------------------------------------------

/// A dispatch entry from the catalog or user config.
#[derive(Debug, Clone, Deserialize)]
pub struct CatalogEntry {
    pub dispatcher: String,
    #[serde(default)]
    pub arg: String,
    pub label: String,
    #[serde(default)]
    pub keywords: Vec<String>,
    #[serde(default)]
    pub arg_template: Option<String>,
    #[serde(default)]
    pub triggers: Vec<String>,
    #[serde(default)]
    pub layout: Option<String>,
}

/// Wrapper for the catalog.toml file format.
#[derive(Debug, Default, Deserialize)]
struct CatalogFile {
    #[serde(default)]
    dispatch: Vec<CatalogEntry>,
}

/// Build a dispatch command ID from dispatcher and arg.
pub fn make_dispatch_id(dispatcher: &str, arg: &str) -> String {
    let trimmed = arg.trim();
    if trimmed.is_empty() {
        return format!("dispatch:{dispatcher}");
    }

    let sanitized: String = trimmed
        .split_whitespace()
        .collect::<Vec<_>>()
        .join(" ");

    let sanitized = if sanitized.len() > 80 {
        sanitized[..80].to_string()
    } else {
        sanitized
    };

    format!("dispatch:{dispatcher}:{sanitized}")
}

// ---------------------------------------------------------------------------
// Top-level config
// ---------------------------------------------------------------------------

#[derive(Debug, Deserialize)]
#[serde(default)]
pub struct Config {
    pub appearance: AppearanceConfig,
    pub scoring: ScoringConfig,
    pub providers: ProvidersConfig,
    pub dispatches: DispatchesConfig,
    pub aliases: HashMap<String, String>,
}

impl Default for Config {
    fn default() -> Self {
        Self {
            appearance: AppearanceConfig::default(),
            scoring: ScoringConfig::default(),
            providers: ProvidersConfig::default(),
            dispatches: DispatchesConfig::default(),
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

    /// Load the dispatch catalog, merge with user additions, filter by layout,
    /// and remove hidden entries.
    pub fn load_catalog(&self) -> Vec<CatalogEntry> {
        // Ensure default catalog exists on disk.
        if let Some(ref data_dir) = Self::data_dir() {
            let catalog_path = data_dir.join("catalog.toml");
            if !catalog_path.exists() {
                let _ = std::fs::create_dir_all(data_dir);
                let _ = std::fs::write(&catalog_path, DEFAULT_CATALOG);
            }
        }

        // Load catalog from disk.
        let mut entries = if let Some(ref data_dir) = Self::data_dir() {
            let catalog_path = data_dir.join("catalog.toml");
            match std::fs::read_to_string(&catalog_path) {
                Ok(text) => match toml::from_str::<CatalogFile>(&text) {
                    Ok(catalog) => catalog.dispatch,
                    Err(e) => {
                        eprintln!("keystroke: failed to parse catalog.toml: {e}");
                        let catalog: CatalogFile =
                            toml::from_str(DEFAULT_CATALOG).unwrap_or_default();
                        catalog.dispatch
                    }
                },
                Err(_) => Vec::new(),
            }
        } else {
            Vec::new()
        };

        // Add user-defined entries.
        entries.extend(self.dispatches.add.clone());

        // Filter by layout.
        let layout = self.dispatches.layout.as_deref();
        entries.retain(|e| match &e.layout {
            None => true,
            Some(l) => layout.map_or(false, |f| f == l),
        });

        // Remove hidden entries.
        if !self.dispatches.hide.ids.is_empty() {
            let hidden: HashSet<&str> =
                self.dispatches.hide.ids.iter().map(|s| s.as_str()).collect();
            entries.retain(|e| {
                let id = make_dispatch_id(&e.dispatcher, &e.arg);
                !hidden.contains(id.as_str())
            });
        }

        entries
    }

    /// Resolve the config file path.
    fn config_path() -> Option<PathBuf> {
        let home = std::env::var("HOME").ok()?;
        Some(PathBuf::from(home).join(".config/keystroke/config.toml"))
    }

    /// Resolve the data directory path.
    fn data_dir() -> Option<PathBuf> {
        let home = std::env::var("HOME").ok()?;
        Some(PathBuf::from(home).join(".local/share/keystroke"))
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
    /// match score.
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
    /// Enable the dispatch command provider.
    pub dispatches: bool,
}

impl Default for ProvidersConfig {
    fn default() -> Self {
        Self { dispatches: true }
    }
}

// ---------------------------------------------------------------------------
// Dispatches
// ---------------------------------------------------------------------------

#[derive(Debug, Deserialize)]
#[serde(default)]
pub struct DispatchesConfig {
    /// Which layout's entries to show (e.g., "scrolling", "dwindle", "master").
    pub layout: Option<String>,
    /// Additional dispatch entries from user config.
    #[serde(default)]
    pub add: Vec<CatalogEntry>,
    /// Entries to hide from the catalog.
    #[serde(default)]
    pub hide: HideConfig,
}

impl Default for DispatchesConfig {
    fn default() -> Self {
        Self {
            layout: None,
            add: Vec::new(),
            hide: HideConfig::default(),
        }
    }
}

#[derive(Debug, Default, Deserialize)]
pub struct HideConfig {
    #[serde(default)]
    pub ids: Vec<String>,
}
