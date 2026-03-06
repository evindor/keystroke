use std::collections::HashMap;
use std::process;

use serde::Deserialize;

use super::{Command, Provider};

/// Raw binding entry as returned by `hyprctl binds -j`.
#[derive(Debug, Deserialize)]
struct RawBinding {
    #[allow(dead_code)]
    locked: bool,
    #[allow(dead_code)]
    mouse: bool,
    #[allow(dead_code)]
    release: bool,
    #[allow(dead_code)]
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

pub struct HyprlandProvider {
    custom_descriptions: HashMap<String, String>,
}

impl HyprlandProvider {
    pub fn new(custom_descriptions: HashMap<String, String>) -> Self {
        Self {
            custom_descriptions,
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
}

impl Provider for HyprlandProvider {
    fn id(&self) -> &str {
        "hyprland"
    }

    fn commands(&self) -> Vec<Command> {
        self.fetch_bindings()
            .iter()
            .map(|b| self.binding_to_command(b))
            .collect()
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
        let provider = HyprlandProvider::new(HashMap::new());
        let binding = RawBinding {
            locked: true,
            mouse: false,
            release: false,
            repeat: true,
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
        let provider = HyprlandProvider::new(custom);
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
}
