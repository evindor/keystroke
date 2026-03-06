use std::path::PathBuf;

// ---------------------------------------------------------------------------
// Default fallback colors (Catppuccin Mocha-ish)
// ---------------------------------------------------------------------------

const DEFAULT_BG: &str = "#1e1e2e";
const DEFAULT_FG: &str = "#cdd6f4";

// ---------------------------------------------------------------------------
// Theme
// ---------------------------------------------------------------------------

#[derive(Debug, Clone)]
pub struct Theme {
    pub background: String,
    pub foreground: String,
}

impl Theme {
    /// Parse `~/.config/omarchy/current/theme/waybar.css` for foreground and
    /// background `@define-color` directives.  Falls back to compiled-in
    /// defaults when the file is missing or the colours cannot be extracted.
    ///
    /// Re-parses on every call so that theme changes take effect without
    /// restarting the launcher.
    pub fn load() -> Self {
        let (bg, fg) = waybar_colors().unwrap_or_else(|| {
            (DEFAULT_BG.to_string(), DEFAULT_FG.to_string())
        });

        Self {
            background: bg,
            foreground: fg,
        }
    }

    /// Produce a complete GTK4 CSS stylesheet for the launcher.
    ///
    /// `border_radius` and `width` are taken from the user's
    /// `AppearanceConfig` (see `config.rs`).
    pub fn generate_css(&self, border_radius: u32, width: u32) -> String {
        build_css(&self.background, &self.foreground, border_radius, width)
    }
}

// ---------------------------------------------------------------------------
// Colour helpers
// ---------------------------------------------------------------------------

/// Convert a hex colour string like `"#2d353b"` to an `rgba(r, g, b, a)`
/// CSS value.  Accepts both 6-digit (`#rrggbb`) and 3-digit (`#rgb`) hex.
pub fn hex_to_rgba(hex: &str, alpha: f64) -> String {
    let hex = hex.trim().trim_start_matches('#');

    let (r, g, b) = match hex.len() {
        6 => {
            let r = u8::from_str_radix(&hex[0..2], 16).unwrap_or(0);
            let g = u8::from_str_radix(&hex[2..4], 16).unwrap_or(0);
            let b = u8::from_str_radix(&hex[4..6], 16).unwrap_or(0);
            (r, g, b)
        }
        3 => {
            let r = u8::from_str_radix(&hex[0..1], 16).unwrap_or(0) * 17;
            let g = u8::from_str_radix(&hex[1..2], 16).unwrap_or(0) * 17;
            let b = u8::from_str_radix(&hex[2..3], 16).unwrap_or(0) * 17;
            (r, g, b)
        }
        _ => (0, 0, 0),
    };

    format!("rgba({}, {}, {}, {:.2})", r, g, b, alpha)
}

/// Lighten a hex colour by `amount` (0.0 .. 1.0) and return a new hex string.
fn lighten_hex(hex: &str, amount: f64) -> String {
    let hex = hex.trim().trim_start_matches('#');
    if hex.len() < 6 {
        return format!("#{}", hex);
    }

    let r = u8::from_str_radix(&hex[0..2], 16).unwrap_or(0) as f64;
    let g = u8::from_str_radix(&hex[2..4], 16).unwrap_or(0) as f64;
    let b = u8::from_str_radix(&hex[4..6], 16).unwrap_or(0) as f64;

    let r = (r + (255.0 - r) * amount).min(255.0) as u8;
    let g = (g + (255.0 - g) * amount).min(255.0) as u8;
    let b = (b + (255.0 - b) * amount).min(255.0) as u8;

    format!("#{:02x}{:02x}{:02x}", r, g, b)
}

// ---------------------------------------------------------------------------
// Waybar CSS parser
// ---------------------------------------------------------------------------

/// Resolve the waybar theme path, expanding `~` via `$HOME`.
fn waybar_css_path() -> Option<PathBuf> {
    let home = std::env::var("HOME").ok()?;
    Some(PathBuf::from(home).join(".config/omarchy/current/theme/waybar.css"))
}

/// Read the waybar CSS and pull out `foreground` / `background` colours.
///
/// Expected lines:
/// ```css
/// @define-color foreground #d3c6aa;
/// @define-color background #2d353b;
/// ```
///
/// Uses simple string splitting -- no regex crate required.
fn waybar_colors() -> Option<(String, String)> {
    let path = waybar_css_path()?;
    let text = std::fs::read_to_string(path).ok()?;

    let mut bg: Option<String> = None;
    let mut fg: Option<String> = None;

    for line in text.lines() {
        let line = line.trim();
        if !line.starts_with("@define-color") {
            continue;
        }

        // Strip the leading directive.
        let rest = line
            .strip_prefix("@define-color")
            .unwrap_or("")
            .trim();

        // `rest` should now look like  `foreground #d3c6aa;`
        // Split on whitespace to get the name and value.
        let mut parts = rest.splitn(2, char::is_whitespace);
        let name = match parts.next() {
            Some(n) => n.trim(),
            None => continue,
        };
        let value = match parts.next() {
            Some(v) => v.trim().trim_end_matches(';').trim(),
            None => continue,
        };

        // Only accept values that look like hex colours.
        if !value.starts_with('#') {
            continue;
        }

        match name {
            "background" => bg = Some(value.to_string()),
            "foreground" => fg = Some(value.to_string()),
            _ => {}
        }
    }

    Some((
        bg.unwrap_or_else(|| DEFAULT_BG.to_string()),
        fg.unwrap_or_else(|| DEFAULT_FG.to_string()),
    ))
}

// ---------------------------------------------------------------------------
// CSS generation
// ---------------------------------------------------------------------------

fn build_css(bg_color: &str, fg_color: &str, border_radius: u32, _width: u32) -> String {
    // Derived colours
    let bg_solid = hex_to_rgba(bg_color, 1.0);
    let bg_semi = hex_to_rgba(bg_color, 0.85);
    let bg_input = hex_to_rgba(bg_color, 0.0);
    let fg_primary = fg_color.to_string();
    let fg_faded = hex_to_rgba(fg_color, 0.50);
    let fg_dimmed = hex_to_rgba(fg_color, 0.30);
    let highlight_bg = hex_to_rgba(fg_color, 0.10);
    let accent = lighten_hex(fg_color, 0.15);
    let shadow_color = hex_to_rgba(bg_color, 0.60);
    let separator_color = hex_to_rgba(fg_color, 0.12);
    let hover_bg = hex_to_rgba(fg_color, 0.06);
    let selected_fg = accent;
    let _ = bg_solid; // used below in template

    format!(
        r#"
/* -----------------------------------------------------------------
   Keystroke launcher -- generated CSS (do not edit by hand)
   bg: {bg_color}  fg: {fg_color}
   ----------------------------------------------------------------- */

/* Main window: fully transparent, no decorations */
window {{
    background-color: transparent;
    background: transparent;
    border: none;
    box-shadow: none;
}}

/* The visible launcher box */
.container {{
    background-color: {bg_semi};
    border-radius: {border_radius}px;
    border: 1px solid {separator_color};
    box-shadow: 0 8px 32px {shadow_color},
                0 2px 8px  {shadow_color};
    padding: 8px 0;
    margin: 0;
}}

/* Search input field */
.search-input {{
    background-color: {bg_input};
    border: none;
    border-radius: 0;
    outline: none;
    box-shadow: none;
    color: {fg_primary};
    font-size: 20px;
    font-weight: 400;
    padding: 12px 20px;
    margin: 0;
    caret-color: {selected_fg};
    min-height: 40px;
}}

.search-input:focus {{
    outline: none;
    box-shadow: none;
    border: none;
}}

/* Thin separator between search input and results */
.separator {{
    background-color: {separator_color};
    min-height: 1px;
    margin: 4px 16px;
}}

/* Scrollable results list */
.results-list {{
    background-color: transparent;
    padding: 4px 0;
    margin: 0;
}}

/* Individual result row */
.result-row {{
    background-color: transparent;
    padding: 8px 20px;
    margin: 0 6px;
    border-radius: {row_radius}px;
    transition: background-color 150ms ease;
}}

.result-row:hover {{
    background-color: {hover_bg};
}}

/* Selected / highlighted result row */
.result-row.selected,
.result-row:selected {{
    background-color: {highlight_bg};
}}

/* Command name (primary text) */
.result-label {{
    color: {fg_primary};
    font-size: 15px;
    font-weight: 400;
}}

.result-row.selected .result-label,
.result-row:selected .result-label {{
    color: {selected_fg};
    font-weight: 500;
}}

/* Hotkey text (secondary, faded, monospace) */
.result-hotkey {{
    color: {fg_faded};
    font-size: 12px;
    font-family: monospace;
    font-weight: 400;
}}

.result-row.selected .result-hotkey,
.result-row:selected .result-hotkey {{
    color: {fg_dimmed};
}}

/* Placeholder text inside search input */
.search-input placeholder {{
    color: {fg_faded};
    font-style: italic;
}}
"#,
        bg_color = bg_color,
        fg_color = fg_color,
        bg_semi = bg_semi,
        bg_input = bg_input,
        fg_primary = fg_primary,
        fg_faded = fg_faded,
        fg_dimmed = fg_dimmed,
        highlight_bg = highlight_bg,
        selected_fg = selected_fg,
        shadow_color = shadow_color,
        separator_color = separator_color,
        hover_bg = hover_bg,
        border_radius = border_radius,
        row_radius = (border_radius / 2).max(4),
    )
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_hex_to_rgba_six_digit() {
        assert_eq!(
            hex_to_rgba("#2d353b", 0.85),
            "rgba(45, 53, 59, 0.85)"
        );
    }

    #[test]
    fn test_hex_to_rgba_three_digit() {
        assert_eq!(
            hex_to_rgba("#fff", 1.0),
            "rgba(255, 255, 255, 1.00)"
        );
    }

    #[test]
    fn test_hex_to_rgba_no_hash() {
        assert_eq!(
            hex_to_rgba("2d353b", 0.5),
            "rgba(45, 53, 59, 0.50)"
        );
    }

    #[test]
    fn test_lighten_hex() {
        // Pure black lightened by 50% should be #7f7f7f (or close).
        let result = lighten_hex("#000000", 0.5);
        assert_eq!(result, "#7f7f7f");
    }

    #[test]
    fn test_lighten_hex_white_stays_white() {
        let result = lighten_hex("#ffffff", 0.5);
        assert_eq!(result, "#ffffff");
    }

    #[test]
    fn test_theme_defaults() {
        // When waybar.css does not exist, we should get defaults.
        let theme = Theme::load();
        // We just verify the struct is populated -- the actual colours depend
        // on whether the file exists in the test environment.
        assert!(!theme.background.is_empty());
        assert!(!theme.foreground.is_empty());
    }

    #[test]
    fn test_generate_css_contains_classes() {
        let theme = Theme {
            background: DEFAULT_BG.to_string(),
            foreground: DEFAULT_FG.to_string(),
        };
        let css = theme.generate_css(16, 680);
        assert!(css.contains("window"));
        assert!(css.contains(".container"));
        assert!(css.contains(".search-input"));
        assert!(css.contains(".results-list"));
        assert!(css.contains(".result-row"));
        assert!(css.contains(".result-row.selected"));
        assert!(css.contains(".result-row:selected"));
        assert!(css.contains(".result-label"));
        assert!(css.contains(".result-hotkey"));
        assert!(css.contains(".separator"));
    }

    #[test]
    fn test_generate_css_uses_dimensions() {
        let theme = Theme {
            background: "#2d353b".to_string(),
            foreground: "#d3c6aa".to_string(),
        };
        let css = theme.generate_css(24, 720);
        assert!(css.contains("border-radius: 24px"));
    }
}
