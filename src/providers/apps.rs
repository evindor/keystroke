use std::collections::{HashMap, HashSet};
use std::path::{Path, PathBuf};
use std::{fs, process};

use super::{Command, Provider};

pub struct AppsProvider;

impl AppsProvider {
    pub fn new() -> Self {
        Self
    }
}

impl Provider for AppsProvider {
    fn id(&self) -> &str {
        "apps"
    }

    fn commands(&self) -> Vec<Command> {
        let entries = scan_desktop_entries();
        entries.into_iter().filter_map(|e| entry_to_command(&e)).collect()
    }

    fn execute(&self, command: &Command) {
        let exec = &command.data;
        if exec.is_empty() {
            return;
        }

        // Check if the command already uses uwsm-app or is an omarchy- wrapper
        let needs_uwsm = !exec.contains("uwsm-app") && !exec.contains("uwsm app");

        let shell_cmd = if needs_uwsm {
            format!("uwsm-app -- {}", exec)
        } else {
            exec.to_string()
        };

        let mut cmd = process::Command::new("sh");
        cmd.args(["-c", &shell_cmd]);
        cmd.stdin(process::Stdio::null());
        cmd.stdout(process::Stdio::null());
        cmd.stderr(process::Stdio::null());
        if let Err(e) = cmd.spawn() {
            eprintln!("apps: failed to launch {}: {e}", command.label);
        }
    }
}

// ---------------------------------------------------------------------------
// Desktop entry parsing
// ---------------------------------------------------------------------------

struct DesktopEntry {
    /// Basename of the .desktop file (e.g. "firefox.desktop")
    filename: String,
    name: String,
    generic_name: String,
    comment: String,
    exec: String,
    icon: String,
    keywords: Vec<String>,
    categories: Vec<String>,
    terminal: bool,
    no_display: bool,
    hidden: bool,
    try_exec: String,
}

/// Scan all desktop entry directories and return parsed entries.
/// User-local entries override system ones (deduped by filename).
fn scan_desktop_entries() -> Vec<DesktopEntry> {
    let home = std::env::var("HOME").unwrap_or_default();

    let dirs = [
        PathBuf::from(&home).join(".local/share/applications"),
        PathBuf::from("/usr/share/applications"),
    ];

    let mut seen: HashSet<String> = HashSet::new();
    let mut entries = Vec::new();

    for dir in &dirs {
        let Ok(read_dir) = fs::read_dir(dir) else {
            continue;
        };
        for entry in read_dir.flatten() {
            let path = entry.path();
            if path.extension().and_then(|e| e.to_str()) != Some("desktop") {
                continue;
            }
            let filename = entry.file_name().to_string_lossy().to_string();

            // User-local overrides system: skip if we've already seen this filename
            if !seen.insert(filename.clone()) {
                continue;
            }

            if let Some(de) = parse_desktop_file(&path, &filename) {
                entries.push(de);
            }
        }
    }

    entries
}

/// Parse a single .desktop file. Returns None if the file can't be read.
fn parse_desktop_file(path: &Path, filename: &str) -> Option<DesktopEntry> {
    let text = fs::read_to_string(path).ok()?;
    let mut in_desktop_entry = false;

    let mut fields: HashMap<String, String> = HashMap::new();

    for line in text.lines() {
        let line = line.trim();

        if line.starts_with('[') {
            in_desktop_entry = line == "[Desktop Entry]";
            continue;
        }

        if !in_desktop_entry || line.is_empty() || line.starts_with('#') {
            continue;
        }

        if let Some((key, value)) = line.split_once('=') {
            // Skip localized keys like Name[fr]
            let key = key.trim();
            if key.contains('[') {
                continue;
            }
            fields.insert(key.to_string(), value.trim().to_string());
        }
    }

    // Must be Type=Application
    if fields.get("Type").map(|s| s.as_str()) != Some("Application") {
        return None;
    }

    let keywords: Vec<String> = fields
        .get("Keywords")
        .unwrap_or(&String::new())
        .split(';')
        .filter(|s| !s.is_empty())
        .map(|s| s.trim().to_lowercase())
        .collect();

    let categories: Vec<String> = fields
        .get("Categories")
        .unwrap_or(&String::new())
        .split(';')
        .filter(|s| !s.is_empty())
        .map(|s| s.trim().to_lowercase())
        .collect();

    Some(DesktopEntry {
        filename: filename.to_string(),
        name: fields.get("Name").cloned().unwrap_or_default(),
        generic_name: fields.get("GenericName").cloned().unwrap_or_default(),
        comment: fields.get("Comment").cloned().unwrap_or_default(),
        exec: fields.get("Exec").cloned().unwrap_or_default(),
        icon: fields.get("Icon").cloned().unwrap_or_default(),
        keywords,
        categories,
        terminal: fields.get("Terminal").map(|v| v == "true").unwrap_or(false),
        no_display: fields.get("NoDisplay").map(|v| v == "true").unwrap_or(false),
        hidden: fields.get("Hidden").map(|v| v == "true").unwrap_or(false),
        try_exec: fields.get("TryExec").cloned().unwrap_or_default(),
    })
}

/// Convert a DesktopEntry into a Command, applying filters.
fn entry_to_command(entry: &DesktopEntry) -> Option<Command> {
    // Filter out hidden/no-display entries
    if entry.hidden || entry.no_display {
        return None;
    }

    // Filter empty names
    if entry.name.is_empty() {
        return None;
    }

    // Filter by TryExec — skip if the binary isn't found
    if !entry.try_exec.is_empty() && !is_in_path(&entry.try_exec) {
        return None;
    }

    // Strip field codes from Exec
    let mut exec = strip_field_codes(&entry.exec);

    // If Terminal=true, wrap with xdg-terminal-exec
    if entry.terminal {
        exec = format!("xdg-terminal-exec -e {}", exec);
    }

    // Build keywords from all searchable fields
    let mut keywords: Vec<String> = entry.keywords.clone();
    keywords.extend(entry.categories.clone());
    if !entry.generic_name.is_empty() {
        keywords.push(entry.generic_name.to_lowercase());
    }
    if !entry.comment.is_empty() {
        // Add significant words from comment
        for word in entry.comment.split_whitespace() {
            if word.len() > 3 {
                keywords.push(word.to_lowercase());
            }
        }
    }
    // Add the filename stem (e.g. "signal-desktop" from "signal-desktop.desktop")
    let stem = entry.filename.strip_suffix(".desktop").unwrap_or(&entry.filename);
    keywords.push(stem.to_lowercase());
    // Split on hyphens/dots for extra matching
    for part in stem.split(&['-', '.'][..]) {
        if !part.is_empty() {
            keywords.push(part.to_lowercase());
        }
    }

    keywords.sort();
    keywords.dedup();

    let icon = if entry.icon.is_empty() {
        None
    } else {
        Some(entry.icon.clone())
    };

    Some(Command {
        id: format!("app:{}", entry.filename),
        label: entry.name.clone(),
        keywords,
        hotkey: None,
        icon,
        provider: "apps".to_string(),
        data: exec,
    })
}

/// Strip desktop entry field codes (%u, %U, %f, %F, %i, %c, %k, %d, %D, %n, %N, %v, %m)
fn strip_field_codes(exec: &str) -> String {
    let mut result = String::with_capacity(exec.len());
    let mut chars = exec.chars().peekable();

    while let Some(c) = chars.next() {
        if c == '%' {
            if let Some(&next) = chars.peek() {
                match next {
                    'u' | 'U' | 'f' | 'F' | 'i' | 'c' | 'k' | 'd' | 'D' | 'n' | 'N' | 'v'
                    | 'm' => {
                        chars.next(); // consume the code character
                        // Also consume trailing space if any
                        if chars.peek() == Some(&' ') {
                            chars.next();
                        }
                        continue;
                    }
                    '%' => {
                        chars.next();
                        result.push('%'); // %% -> literal %
                        continue;
                    }
                    _ => {}
                }
            }
        }
        result.push(c);
    }

    result.trim().to_string()
}

/// Check if a binary name is available in $PATH.
fn is_in_path(binary: &str) -> bool {
    if let Ok(path_var) = std::env::var("PATH") {
        for dir in path_var.split(':') {
            if Path::new(dir).join(binary).exists() {
                return true;
            }
        }
    }
    false
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_strip_field_codes() {
        assert_eq!(strip_field_codes("firefox %u"), "firefox");
        assert_eq!(strip_field_codes("firefox %U"), "firefox");
        assert_eq!(
            strip_field_codes("/opt/1Password/1password %U"),
            "/opt/1Password/1password"
        );
        assert_eq!(strip_field_codes("code --new-window %F"), "code --new-window");
        assert_eq!(strip_field_codes("app"), "app");
        assert_eq!(strip_field_codes("app %%"), "app %");
    }

    #[test]
    fn test_is_in_path() {
        assert!(is_in_path("sh")); // sh is always in PATH
        assert!(!is_in_path("nonexistent_binary_xyz_12345"));
    }

    #[test]
    fn test_entry_to_command_filters_hidden() {
        let entry = DesktopEntry {
            filename: "test.desktop".into(),
            name: "Test".into(),
            generic_name: String::new(),
            comment: String::new(),
            exec: "test".into(),
            icon: String::new(),
            keywords: vec![],
            categories: vec![],
            terminal: false,
            no_display: false,
            hidden: true,
            try_exec: String::new(),
        };
        assert!(entry_to_command(&entry).is_none());
    }

    #[test]
    fn test_entry_to_command_basic() {
        let entry = DesktopEntry {
            filename: "firefox.desktop".into(),
            name: "Firefox".into(),
            generic_name: "Web Browser".into(),
            comment: "Browse the web".into(),
            exec: "firefox %u".into(),
            icon: "firefox".into(),
            keywords: vec!["internet".into()],
            categories: vec!["network".into()],
            terminal: false,
            no_display: false,
            hidden: false,
            try_exec: String::new(),
        };
        let cmd = entry_to_command(&entry).unwrap();
        assert_eq!(cmd.id, "app:firefox.desktop");
        assert_eq!(cmd.label, "Firefox");
        assert_eq!(cmd.data, "firefox");
        assert_eq!(cmd.icon, Some("firefox".to_string()));
        assert!(cmd.keywords.contains(&"web browser".to_string()));
        assert!(cmd.keywords.contains(&"internet".to_string()));
        assert!(cmd.keywords.contains(&"firefox".to_string()));
    }

    #[test]
    fn test_entry_to_command_terminal() {
        let entry = DesktopEntry {
            filename: "btop.desktop".into(),
            name: "btop++".into(),
            generic_name: String::new(),
            comment: String::new(),
            exec: "btop".into(),
            icon: "btop".into(),
            keywords: vec![],
            categories: vec![],
            terminal: true,
            no_display: false,
            hidden: false,
            try_exec: String::new(),
        };
        let cmd = entry_to_command(&entry).unwrap();
        assert_eq!(cmd.data, "xdg-terminal-exec -e btop");
    }
}
