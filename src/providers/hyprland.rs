use std::collections::{HashMap, HashSet};
use std::process;

use serde::Deserialize;

use super::{Command, Provider};
use crate::config::CustomCommand;

// ---------------------------------------------------------------------------
// Noise filtering
// ---------------------------------------------------------------------------

/// Dispatchers to exclude from bound bindings (noisy incremental commands).
const EXCLUDED_DISPATCHERS: &[&str] = &["resizeactive"];

/// A default catalog entry for dispatchers that aren't typically bound.
struct CatalogEntry {
    dispatcher: &'static str,
    arg: &'static str,
    label: &'static str,
    keywords: &'static [&'static str],
    arg_template: Option<&'static str>,
    triggers: &'static [&'static str],
}

/// Default catalog of useful dispatchers that are rarely bound to keys.
const DEFAULT_CATALOG: &[CatalogEntry] = &[
    // One-shot commands (no args needed)
    CatalogEntry {
        dispatcher: "pin",
        arg: "",
        label: "Pin window to all workspaces",
        keywords: &["pin", "sticky"],
        arg_template: None,
        triggers: &[],
    },
    CatalogEntry {
        dispatcher: "centerwindow",
        arg: "",
        label: "Center floating window",
        keywords: &["center", "middle"],
        arg_template: None,
        triggers: &[],
    },
    CatalogEntry {
        dispatcher: "dpms",
        arg: "off",
        label: "Turn off monitors",
        keywords: &["dpms", "monitor", "screen", "off"],
        arg_template: None,
        triggers: &[],
    },
    CatalogEntry {
        dispatcher: "dpms",
        arg: "on",
        label: "Turn on monitors",
        keywords: &["dpms", "monitor", "screen", "on"],
        arg_template: None,
        triggers: &[],
    },
    CatalogEntry {
        dispatcher: "forcekillactive",
        arg: "",
        label: "Force kill active window",
        keywords: &["force", "kill", "xkill"],
        arg_template: None,
        triggers: &[],
    },
    CatalogEntry {
        dispatcher: "settiled",
        arg: "",
        label: "Set window to tiled",
        keywords: &["tile", "tiled", "untile"],
        arg_template: None,
        triggers: &[],
    },
    CatalogEntry {
        dispatcher: "setfloating",
        arg: "",
        label: "Set window to floating",
        keywords: &["float", "floating"],
        arg_template: None,
        triggers: &[],
    },
    CatalogEntry {
        dispatcher: "toggleswallow",
        arg: "",
        label: "Toggle window swallowing",
        keywords: &["swallow"],
        arg_template: None,
        triggers: &[],
    },
    CatalogEntry {
        dispatcher: "forcerendererreload",
        arg: "",
        label: "Force reload renderer",
        keywords: &["renderer", "reload", "refresh"],
        arg_template: None,
        triggers: &[],
    },
    CatalogEntry {
        dispatcher: "lockgroups",
        arg: "toggle",
        label: "Toggle group lock",
        keywords: &["lock", "group"],
        arg_template: None,
        triggers: &[],
    },
    CatalogEntry {
        dispatcher: "lockactivegroup",
        arg: "toggle",
        label: "Toggle active group lock",
        keywords: &["lock", "active", "group"],
        arg_template: None,
        triggers: &[],
    },
    CatalogEntry {
        dispatcher: "focusurgentorlast",
        arg: "",
        label: "Focus urgent or last window",
        keywords: &["urgent", "last", "focus"],
        arg_template: None,
        triggers: &[],
    },
    CatalogEntry {
        dispatcher: "focuscurrentorlast",
        arg: "",
        label: "Focus current or last window",
        keywords: &["current", "last", "focus"],
        arg_template: None,
        triggers: &[],
    },
    CatalogEntry {
        dispatcher: "exit",
        arg: "",
        label: "Exit Hyprland",
        keywords: &["exit", "quit", "logout"],
        arg_template: None,
        triggers: &[],
    },
    // Parameterized commands
    CatalogEntry {
        dispatcher: "renameworkspace",
        arg: "",
        label: "Rename workspace",
        keywords: &["rename", "name", "workspace"],
        arg_template: Some("{active_workspace} {input}"),
        triggers: &["rw", "rename"],
    },
];

// ---------------------------------------------------------------------------
// Raw binding from hyprctl
// ---------------------------------------------------------------------------

/// Raw binding entry as returned by `hyprctl binds -j`.
#[derive(Debug, Deserialize)]
struct RawBinding {
    #[allow(dead_code)]
    locked: bool,
    mouse: bool,
    #[allow(dead_code)]
    release: bool,
    repeat: bool,
    #[allow(dead_code)]
    #[serde(rename = "longPress")]
    long_press: bool,
    #[allow(dead_code)]
    non_consuming: bool,
    has_description: bool,
    modmask: u32,
    #[allow(dead_code)]
    submap: String,
    key: String,
    #[allow(dead_code)]
    keycode: i32,
    #[allow(dead_code)]
    catch_all: bool,
    description: String,
    dispatcher: String,
    arg: String,
}

// ---------------------------------------------------------------------------
// Resolved parameterized command (catalog or user-defined)
// ---------------------------------------------------------------------------

struct ParameterizedCommand {
    dispatcher: String,
    label: String,
    arg_template: String,
    triggers: Vec<String>,
}

// ---------------------------------------------------------------------------
// Provider
// ---------------------------------------------------------------------------

pub struct HyprlandProvider {
    custom_descriptions: HashMap<String, String>,
    user_commands: Vec<CustomCommand>,
}

impl HyprlandProvider {
    pub fn new(
        custom_descriptions: HashMap<String, String>,
        user_commands: Vec<CustomCommand>,
    ) -> Self {
        Self {
            custom_descriptions,
            user_commands,
        }
    }

    /// Run `hyprctl binds -j` and parse the JSON output into raw bindings.
    fn fetch_bindings(&self) -> Vec<RawBinding> {
        let output = match process::Command::new("hyprctl")
            .args(["binds", "-j"])
            .output()
        {
            Ok(o) => o,
            Err(e) => {
                eprintln!("hyprland: failed to run hyprctl binds -j: {e}");
                return Vec::new();
            }
        };

        if !output.status.success() {
            eprintln!(
                "hyprland: hyprctl binds -j exited with {}",
                output.status
            );
            return Vec::new();
        }

        match serde_json::from_slice::<Vec<RawBinding>>(&output.stdout) {
            Ok(bindings) => bindings,
            Err(e) => {
                eprintln!("hyprland: failed to parse hyprctl JSON: {e}");
                Vec::new()
            }
        }
    }

    /// Returns true if a binding should be filtered out as noise.
    fn is_noisy(binding: &RawBinding) -> bool {
        if binding.repeat {
            return true;
        }
        if binding.mouse {
            return true;
        }
        if binding.key.starts_with("mouse_") {
            return true;
        }
        if EXCLUDED_DISPATCHERS.contains(&binding.dispatcher.as_str()) {
            return true;
        }
        false
    }

    /// Decode the modmask bitmask into a list of modifier names.
    fn decode_modmask(modmask: u32) -> Vec<&'static str> {
        let mut mods = Vec::new();
        if modmask & 64 != 0 {
            mods.push("SUPER");
        }
        if modmask & 4 != 0 {
            mods.push("CTRL");
        }
        if modmask & 8 != 0 {
            mods.push("ALT");
        }
        if modmask & 1 != 0 {
            mods.push("SHIFT");
        }
        mods
    }

    /// Format modifiers + key into a human-readable hotkey string like "SUPER + SHIFT + W".
    fn format_hotkey(modmask: u32, key: &str) -> Option<String> {
        if key.is_empty() && modmask == 0 {
            return None;
        }
        let mut parts = Self::decode_modmask(modmask);
        if !key.is_empty() {
            parts.push(key);
        }
        if parts.is_empty() {
            return None;
        }
        Some(parts.join(" + "))
    }

    /// Build a command ID from dispatcher and arg.
    /// Format: "hyprland:{dispatcher}:{sanitized_arg}" or "hyprland:{dispatcher}" if no arg.
    fn make_command_id(dispatcher: &str, arg: &str) -> String {
        let trimmed = arg.trim();
        if trimmed.is_empty() {
            return format!("hyprland:{dispatcher}");
        }

        // Collapse whitespace and trim long args to keep IDs reasonable.
        let sanitized: String = trimmed
            .split_whitespace()
            .collect::<Vec<_>>()
            .join(" ");

        let sanitized = if sanitized.len() > 80 {
            sanitized[..80].to_string()
        } else {
            sanitized
        };

        format!("hyprland:{dispatcher}:{sanitized}")
    }

    /// Build the execution data string: "{dispatcher} {arg}" or just "{dispatcher}".
    fn make_data(dispatcher: &str, arg: &str) -> String {
        let trimmed = arg.trim();
        if trimmed.is_empty() {
            dispatcher.to_string()
        } else {
            format!("{dispatcher} {trimmed}")
        }
    }

    /// Auto-generate a label from the dispatcher and its argument.
    ///
    /// For `exec` commands, we extract the script/binary name from the arg path and
    /// attempt to produce a friendlier label (e.g. "omarchy-launch-browser" -> "Launch browser").
    /// For everything else, return "{dispatcher} {arg}" or just "{dispatcher}".
    fn auto_label(dispatcher: &str, arg: &str) -> String {
        let trimmed = arg.trim();

        if dispatcher == "exec" && !trimmed.is_empty() {
            // The arg may be a full command line; take the first token as the binary.
            let binary = trimmed.split_whitespace().next().unwrap_or(trimmed);
            // Strip any leading path components.
            let name = binary.rsplit('/').next().unwrap_or(binary);
            let friendly = humanize_binary_name(name);
            if friendly.is_empty() {
                return "exec".to_string();
            }
            return friendly;
        }

        if trimmed.is_empty() {
            dispatcher.to_string()
        } else {
            format!("{dispatcher} {trimmed}")
        }
    }

    /// Collect extra searchable keywords from a binding.
    fn make_keywords(dispatcher: &str, key: &str, arg: &str) -> Vec<String> {
        let mut kw = Vec::new();

        kw.push(dispatcher.to_string());

        if !key.is_empty() {
            kw.push(key.to_lowercase());
        }

        // For exec args, include path components of the binary as keywords.
        let trimmed = arg.trim();
        if !trimmed.is_empty() {
            let binary = trimmed.split_whitespace().next().unwrap_or(trimmed);
            for component in binary.split('/') {
                if !component.is_empty() {
                    kw.push(component.to_lowercase());
                }
            }
            // Also include the full binary name with hyphens split.
            let name = binary.rsplit('/').next().unwrap_or(binary);
            for part in name.split('-') {
                if !part.is_empty() {
                    kw.push(part.to_lowercase());
                }
            }
        }

        kw.sort();
        kw.dedup();
        kw
    }

    /// Convert a single raw binding into a Command.
    fn binding_to_command(&self, binding: &RawBinding) -> Command {
        let id = Self::make_command_id(&binding.dispatcher, &binding.arg);

        let label = if let Some(custom) = self.custom_descriptions.get(&id) {
            custom.clone()
        } else if binding.has_description && !binding.description.trim().is_empty() {
            binding.description.trim().to_string()
        } else {
            Self::auto_label(&binding.dispatcher, &binding.arg)
        };

        let hotkey = Self::format_hotkey(binding.modmask, &binding.key);
        let keywords = Self::make_keywords(&binding.dispatcher, &binding.key, &binding.arg);
        let data = Self::make_data(&binding.dispatcher, &binding.arg);

        Command {
            id,
            label,
            keywords,
            hotkey,
            icon: None,
            provider: "hyprland".to_string(),
            data,
        }
    }

    /// Build the list of parameterized commands from catalog defaults + user config.
    fn parameterized_commands(&self) -> Vec<ParameterizedCommand> {
        let mut result = Vec::new();

        // User-defined commands with arg_template override catalog entries.
        let user_dispatchers: HashSet<String> = self
            .user_commands
            .iter()
            .filter(|c| c.arg_template.is_some())
            .map(|c| Self::make_command_id(&c.dispatcher, &c.arg))
            .collect();

        // Catalog parameterized entries.
        for entry in DEFAULT_CATALOG {
            let Some(template) = entry.arg_template else {
                continue;
            };
            let id = Self::make_command_id(entry.dispatcher, entry.arg);
            if user_dispatchers.contains(&id) {
                continue; // User override takes precedence.
            }
            result.push(ParameterizedCommand {
                dispatcher: entry.dispatcher.to_string(),
                label: entry.label.to_string(),
                arg_template: template.to_string(),
                triggers: entry.triggers.iter().map(|s| s.to_string()).collect(),
            });
        }

        // User-defined parameterized commands.
        for cmd in &self.user_commands {
            if let Some(ref template) = cmd.arg_template {
                if cmd.hidden {
                    continue;
                }
                result.push(ParameterizedCommand {
                    dispatcher: cmd.dispatcher.clone(),
                    label: cmd.label.clone(),
                    arg_template: template.clone(),
                    triggers: cmd
                        .keywords
                        .iter()
                        .filter(|k| k.len() <= 8) // Short keywords double as triggers.
                        .cloned()
                        .collect(),
                });
            }
        }

        result
    }

    /// Query `hyprctl activeworkspace -j` to get the current workspace ID.
    fn active_workspace_id() -> Option<i64> {
        let output = process::Command::new("hyprctl")
            .args(["activeworkspace", "-j"])
            .output()
            .ok()?;

        if !output.status.success() {
            return None;
        }

        #[derive(Deserialize)]
        struct Workspace {
            id: i64,
        }

        let ws: Workspace = serde_json::from_slice(&output.stdout).ok()?;
        Some(ws.id)
    }

    /// Resolve template variables in an arg_template.
    fn resolve_template(template: &str, input: &str) -> String {
        let mut result = template.replace("{input}", input);
        if result.contains("{active_workspace}") {
            let ws_id = Self::active_workspace_id()
                .map(|id| id.to_string())
                .unwrap_or_else(|| "1".to_string());
            result = result.replace("{active_workspace}", &ws_id);
        }
        result
    }
}

impl Provider for HyprlandProvider {
    fn id(&self) -> &str {
        "hyprland"
    }

    fn commands(&self) -> Vec<Command> {
        let mut seen_ids: HashSet<String> = HashSet::new();
        let mut commands = Vec::new();

        // Collect user-hidden IDs.
        let hidden_ids: HashSet<String> = self
            .user_commands
            .iter()
            .filter(|c| c.hidden)
            .map(|c| Self::make_command_id(&c.dispatcher, &c.arg))
            .collect();

        // 1. Fetch bound bindings, filter noise.
        for binding in self.fetch_bindings() {
            if Self::is_noisy(&binding) {
                continue;
            }
            let cmd = self.binding_to_command(&binding);
            if hidden_ids.contains(&cmd.id) {
                continue;
            }
            seen_ids.insert(cmd.id.clone());
            commands.push(cmd);
        }

        // 2. User custom commands (non-hidden, non-parameterized-only).
        for user_cmd in &self.user_commands {
            if user_cmd.hidden {
                continue;
            }
            let id = Self::make_command_id(&user_cmd.dispatcher, &user_cmd.arg);
            if seen_ids.contains(&id) {
                // User override for a bound command: replace it.
                if let Some(existing) = commands.iter_mut().find(|c| c.id == id) {
                    existing.label = user_cmd.label.clone();
                    if !user_cmd.keywords.is_empty() {
                        existing.keywords = user_cmd.keywords.clone();
                        existing.keywords.push(user_cmd.dispatcher.clone());
                    }
                }
                continue;
            }
            // New command from user config.
            let mut keywords = user_cmd.keywords.clone();
            keywords.push(user_cmd.dispatcher.clone());
            keywords.sort();
            keywords.dedup();
            let data = Self::make_data(&user_cmd.dispatcher, &user_cmd.arg);
            commands.push(Command {
                id: id.clone(),
                label: user_cmd.label.clone(),
                keywords,
                hotkey: None,
                icon: None,
                provider: "hyprland".to_string(),
                data,
            });
            seen_ids.insert(id);
        }

        // 3. Default catalog (skip if already seen or hidden).
        for entry in DEFAULT_CATALOG {
            let id = Self::make_command_id(entry.dispatcher, entry.arg);
            if seen_ids.contains(&id) || hidden_ids.contains(&id) {
                continue;
            }
            let mut keywords: Vec<String> = entry.keywords.iter().map(|s| s.to_string()).collect();
            keywords.push(entry.dispatcher.to_string());
            keywords.sort();
            keywords.dedup();
            let data = Self::make_data(entry.dispatcher, entry.arg);
            commands.push(Command {
                id: id.clone(),
                label: entry.label.to_string(),
                keywords,
                hotkey: None,
                icon: None,
                provider: "hyprland".to_string(),
                data,
            });
            seen_ids.insert(id);
        }

        commands
    }

    fn query_commands(&self, query: &str) -> Vec<Command> {
        let query = query.trim();
        if query.is_empty() {
            return Vec::new();
        }

        let mut results = Vec::new();

        for pcmd in self.parameterized_commands() {
            for trigger in &pcmd.triggers {
                let prefix = format!("{trigger} ");
                if let Some(input) = query.strip_prefix(&prefix) {
                    let input = input.trim();
                    if input.is_empty() {
                        continue;
                    }
                    let resolved_arg = Self::resolve_template(&pcmd.arg_template, input);
                    let data = Self::make_data(&pcmd.dispatcher, &resolved_arg);
                    let label = format!("{} \u{2192} '{input}'", pcmd.label);
                    let id = format!(
                        "hyprland:{}:{}",
                        pcmd.dispatcher,
                        resolved_arg.split_whitespace().collect::<Vec<_>>().join(" ")
                    );

                    results.push(Command {
                        id,
                        label,
                        keywords: vec![trigger.clone(), pcmd.dispatcher.clone()],
                        hotkey: None,
                        icon: None,
                        provider: "hyprland".to_string(),
                        data,
                    });
                }
            }
        }

        results
    }

    fn execute(&self, command: &Command) {
        // data is formatted as "{dispatcher} {arg}" or just "{dispatcher}".
        let mut parts = command.data.splitn(2, ' ');
        let dispatcher = parts.next().unwrap_or("");
        let arg = parts.next().unwrap_or("");

        let mut cmd = process::Command::new("hyprctl");
        cmd.args(["dispatch", dispatcher]);
        if !arg.is_empty() {
            cmd.arg(arg);
        }

        // Detach: redirect stdio to null so the child doesn't hold our handles,
        // and don't wait for it.
        cmd.stdin(process::Stdio::null());
        cmd.stdout(process::Stdio::null());
        cmd.stderr(process::Stdio::null());

        match cmd.spawn() {
            Ok(_child) => {
                // Child is detached; we intentionally drop it without waiting.
            }
            Err(e) => {
                eprintln!("hyprland: failed to dispatch {}: {e}", command.data);
            }
        }
    }
}

/// Turn a binary name like "omarchy-launch-browser" into a friendlier label
/// like "Launch browser".
///
/// Strategy:
/// - Strip common prefixes (e.g. "omarchy-").
/// - Split on hyphens.
/// - Capitalize the first word, lowercase the rest.
fn humanize_binary_name(name: &str) -> String {
    let stripped = name
        .strip_prefix("omarchy-")
        .unwrap_or(name);

    let words: Vec<&str> = stripped
        .split('-')
        .filter(|w| !w.is_empty())
        .collect();

    if words.is_empty() {
        return String::new();
    }

    let mut result = String::new();
    for (i, word) in words.iter().enumerate() {
        if i > 0 {
            result.push(' ');
        }
        if i == 0 {
            // Capitalize first letter of first word.
            let mut chars = word.chars();
            if let Some(first) = chars.next() {
                result.extend(first.to_uppercase());
                result.push_str(&chars.as_str().to_lowercase());
            }
        } else {
            result.push_str(&word.to_lowercase());
        }
    }

    result
}

#[cfg(test)]
mod tests {
    use super::*;

    fn make_provider() -> HyprlandProvider {
        HyprlandProvider::new(HashMap::new(), Vec::new())
    }

    #[test]
    fn test_decode_modmask() {
        assert_eq!(HyprlandProvider::decode_modmask(0), Vec::<&str>::new());
        assert_eq!(HyprlandProvider::decode_modmask(64), vec!["SUPER"]);
        assert_eq!(HyprlandProvider::decode_modmask(65), vec!["SUPER", "SHIFT"]);
        assert_eq!(HyprlandProvider::decode_modmask(68), vec!["SUPER", "CTRL"]);
        assert_eq!(HyprlandProvider::decode_modmask(72), vec!["SUPER", "ALT"]);
        assert_eq!(
            HyprlandProvider::decode_modmask(73),
            vec!["SUPER", "ALT", "SHIFT"]
        );
    }

    #[test]
    fn test_format_hotkey() {
        assert_eq!(
            HyprlandProvider::format_hotkey(64, "W"),
            Some("SUPER + W".to_string())
        );
        assert_eq!(
            HyprlandProvider::format_hotkey(65, "Return"),
            Some("SUPER + SHIFT + Return".to_string())
        );
        assert_eq!(HyprlandProvider::format_hotkey(0, ""), None);
    }

    #[test]
    fn test_make_command_id() {
        assert_eq!(
            HyprlandProvider::make_command_id("killactive", ""),
            "hyprland:killactive"
        );
        assert_eq!(
            HyprlandProvider::make_command_id("exec", "omarchy-launch-browser"),
            "hyprland:exec:omarchy-launch-browser"
        );
        assert_eq!(
            HyprlandProvider::make_command_id("exec", "  some   spaced   arg  "),
            "hyprland:exec:some spaced arg"
        );
    }

    #[test]
    fn test_auto_label() {
        assert_eq!(
            HyprlandProvider::auto_label("killactive", ""),
            "killactive"
        );
        assert_eq!(
            HyprlandProvider::auto_label("exec", "omarchy-launch-browser"),
            "Launch browser"
        );
        assert_eq!(
            HyprlandProvider::auto_label("exec", "/usr/bin/omarchy-launch-browser"),
            "Launch browser"
        );
        assert_eq!(
            HyprlandProvider::auto_label("exec", "firefox"),
            "Firefox"
        );
        assert_eq!(
            HyprlandProvider::auto_label("workspace", "3"),
            "workspace 3"
        );
    }

    #[test]
    fn test_humanize_binary_name() {
        assert_eq!(humanize_binary_name("omarchy-launch-browser"), "Launch browser");
        assert_eq!(humanize_binary_name("firefox"), "Firefox");
        assert_eq!(humanize_binary_name("my-cool-app"), "My cool app");
        assert_eq!(humanize_binary_name(""), "");
    }

    #[test]
    fn test_make_keywords() {
        let kw = HyprlandProvider::make_keywords("exec", "W", "omarchy-launch-browser");
        assert!(kw.contains(&"exec".to_string()));
        assert!(kw.contains(&"w".to_string()));
        assert!(kw.contains(&"launch".to_string()));
        assert!(kw.contains(&"browser".to_string()));
    }

    #[test]
    fn test_binding_to_command_with_description() {
        let provider = make_provider();
        let binding = RawBinding {
            locked: true,
            mouse: false,
            release: false,
            repeat: false,
            long_press: false,
            non_consuming: false,
            has_description: true,
            modmask: 64,
            submap: String::new(),
            key: "W".to_string(),
            keycode: 0,
            catch_all: false,
            description: "Close window".to_string(),
            dispatcher: "killactive".to_string(),
            arg: String::new(),
        };

        let cmd = provider.binding_to_command(&binding);
        assert_eq!(cmd.id, "hyprland:killactive");
        assert_eq!(cmd.label, "Close window");
        assert_eq!(cmd.hotkey, Some("SUPER + W".to_string()));
        assert_eq!(cmd.provider, "hyprland");
        assert_eq!(cmd.data, "killactive");
    }

    #[test]
    fn test_binding_to_command_custom_description_overrides() {
        let mut custom = HashMap::new();
        custom.insert(
            "hyprland:killactive".to_string(),
            "My custom close".to_string(),
        );
        let provider = HyprlandProvider::new(custom, Vec::new());
        let binding = RawBinding {
            locked: false,
            mouse: false,
            release: false,
            repeat: false,
            long_press: false,
            non_consuming: false,
            has_description: true,
            modmask: 64,
            submap: String::new(),
            key: "W".to_string(),
            keycode: 0,
            catch_all: false,
            description: "Close window".to_string(),
            dispatcher: "killactive".to_string(),
            arg: String::new(),
        };

        let cmd = provider.binding_to_command(&binding);
        assert_eq!(cmd.label, "My custom close");
    }

    #[test]
    fn test_noise_filter_repeat() {
        let binding = RawBinding {
            locked: false,
            mouse: false,
            release: false,
            repeat: true,
            long_press: false,
            non_consuming: false,
            has_description: false,
            modmask: 64,
            submap: String::new(),
            key: "XF86AudioRaiseVolume".to_string(),
            keycode: 0,
            catch_all: false,
            description: String::new(),
            dispatcher: "exec".to_string(),
            arg: "volume-up".to_string(),
        };
        assert!(HyprlandProvider::is_noisy(&binding));
    }

    #[test]
    fn test_noise_filter_mouse() {
        let binding = RawBinding {
            locked: false,
            mouse: true,
            release: false,
            repeat: false,
            long_press: false,
            non_consuming: false,
            has_description: false,
            modmask: 64,
            submap: String::new(),
            key: "mouse:272".to_string(),
            keycode: 0,
            catch_all: false,
            description: String::new(),
            dispatcher: "movewindow".to_string(),
            arg: String::new(),
        };
        assert!(HyprlandProvider::is_noisy(&binding));
    }

    #[test]
    fn test_noise_filter_mouse_key() {
        let binding = RawBinding {
            locked: false,
            mouse: false,
            release: false,
            repeat: false,
            long_press: false,
            non_consuming: false,
            has_description: false,
            modmask: 64,
            submap: String::new(),
            key: "mouse_up".to_string(),
            keycode: 0,
            catch_all: false,
            description: String::new(),
            dispatcher: "workspace".to_string(),
            arg: "e+1".to_string(),
        };
        assert!(HyprlandProvider::is_noisy(&binding));
    }

    #[test]
    fn test_noise_filter_excluded_dispatcher() {
        let binding = RawBinding {
            locked: false,
            mouse: false,
            release: false,
            repeat: false,
            long_press: false,
            non_consuming: false,
            has_description: false,
            modmask: 64,
            submap: String::new(),
            key: "right".to_string(),
            keycode: 0,
            catch_all: false,
            description: String::new(),
            dispatcher: "resizeactive".to_string(),
            arg: "40 0".to_string(),
        };
        assert!(HyprlandProvider::is_noisy(&binding));
    }

    #[test]
    fn test_noise_filter_normal_binding_passes() {
        let binding = RawBinding {
            locked: false,
            mouse: false,
            release: false,
            repeat: false,
            long_press: false,
            non_consuming: false,
            has_description: true,
            modmask: 64,
            submap: String::new(),
            key: "W".to_string(),
            keycode: 0,
            catch_all: false,
            description: "Close window".to_string(),
            dispatcher: "killactive".to_string(),
            arg: String::new(),
        };
        assert!(!HyprlandProvider::is_noisy(&binding));
    }

    #[test]
    fn test_query_commands_parameterized() {
        let provider = make_provider();
        let results = provider.query_commands("rw awesome");
        assert_eq!(results.len(), 1);
        assert!(results[0].label.contains("awesome"));
        assert!(results[0].data.starts_with("renameworkspace"));
    }

    #[test]
    fn test_query_commands_no_match() {
        let provider = make_provider();
        let results = provider.query_commands("something random");
        assert!(results.is_empty());
    }

    #[test]
    fn test_query_commands_trigger_only_no_input() {
        let provider = make_provider();
        let results = provider.query_commands("rw ");
        assert!(results.is_empty());
    }

    #[test]
    fn test_resolve_template_input_only() {
        let result = HyprlandProvider::resolve_template("{input}", "hello");
        assert_eq!(result, "hello");
    }

    #[test]
    fn test_catalog_entry_present() {
        // Verify the catalog includes key entries.
        let dispatchers: Vec<&str> = DEFAULT_CATALOG.iter().map(|e| e.dispatcher).collect();
        assert!(dispatchers.contains(&"pin"));
        assert!(dispatchers.contains(&"centerwindow"));
        assert!(dispatchers.contains(&"exit"));
        assert!(dispatchers.contains(&"renameworkspace"));
    }

    #[test]
    fn test_user_command_hidden() {
        let user_cmds = vec![CustomCommand {
            dispatcher: "exit".to_string(),
            arg: String::new(),
            label: "Exit Hyprland".to_string(),
            keywords: Vec::new(),
            arg_template: None,
            hidden: true,
        }];
        let provider = HyprlandProvider::new(HashMap::new(), user_cmds);
        // commands() calls hyprctl which won't work in tests, but we can
        // verify the hidden set logic by checking parameterized_commands.
        let pcmds = provider.parameterized_commands();
        // "exit" isn't parameterized so this just verifies no crash.
        assert!(!pcmds.is_empty()); // renameworkspace still there
    }

    #[test]
    fn test_user_parameterized_overrides_catalog() {
        let user_cmds = vec![CustomCommand {
            dispatcher: "renameworkspace".to_string(),
            arg: String::new(),
            label: "My rename".to_string(),
            keywords: vec!["rn".to_string()],
            arg_template: Some("{active_workspace} {input}".to_string()),
            hidden: false,
        }];
        let provider = HyprlandProvider::new(HashMap::new(), user_cmds);
        let pcmds = provider.parameterized_commands();
        let rw: Vec<_> = pcmds.iter().filter(|p| p.dispatcher == "renameworkspace").collect();
        assert_eq!(rw.len(), 1);
        assert_eq!(rw[0].label, "My rename");
        assert!(rw[0].triggers.contains(&"rn".to_string()));
    }
}
