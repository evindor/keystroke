use std::process;

use serde::Deserialize;

use super::{Command, Provider};
use crate::config::{make_dispatch_id, CatalogEntry};

// ---------------------------------------------------------------------------
// Provider
// ---------------------------------------------------------------------------

pub struct DispatchProvider {
    entries: Vec<CatalogEntry>,
}

impl DispatchProvider {
    pub fn new(entries: Vec<CatalogEntry>) -> Self {
        Self { entries }
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

impl Provider for DispatchProvider {
    fn id(&self) -> &str {
        "dispatch"
    }

    fn commands(&self) -> Vec<Command> {
        let mut commands = Vec::new();

        for entry in &self.entries {
            // Parameterized entries are handled by query_commands().
            if entry.arg_template.is_some() {
                continue;
            }

            let id = make_dispatch_id(&entry.dispatcher, &entry.arg);
            let data = Self::make_data(&entry.dispatcher, &entry.arg);
            let mut keywords = entry.keywords.clone();
            keywords.push(entry.dispatcher.clone());
            keywords.sort();
            keywords.dedup();

            commands.push(Command {
                id,
                label: entry.label.clone(),
                keywords,
                hotkey: None,
                icon: None,
                provider: "dispatch".to_string(),
                data,
            });
        }

        commands
    }

    fn query_commands(&self, query: &str) -> Vec<Command> {
        let query = query.trim();
        if query.is_empty() {
            return Vec::new();
        }

        let mut results = Vec::new();

        for entry in &self.entries {
            let Some(ref template) = entry.arg_template else {
                continue;
            };

            for trigger in &entry.triggers {
                let prefix = format!("{trigger} ");
                if let Some(input) = query.strip_prefix(&prefix) {
                    let input = input.trim();
                    if input.is_empty() {
                        continue;
                    }
                    let resolved_arg = Self::resolve_template(template, input);
                    let data = Self::make_data(&entry.dispatcher, &resolved_arg);
                    let label = format!("{} \u{2192} '{input}'", entry.label);
                    let id = make_dispatch_id(&entry.dispatcher, &resolved_arg);

                    results.push(Command {
                        id,
                        label,
                        keywords: vec![trigger.clone(), entry.dispatcher.clone()],
                        hotkey: None,
                        icon: None,
                        provider: "dispatch".to_string(),
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

        cmd.stdin(process::Stdio::null());
        cmd.stdout(process::Stdio::null());
        cmd.stderr(process::Stdio::null());

        match cmd.spawn() {
            Ok(_child) => {}
            Err(e) => {
                eprintln!("dispatch: failed to dispatch {}: {e}", command.data);
            }
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn make_entry(
        dispatcher: &str,
        arg: &str,
        label: &str,
        keywords: Vec<&str>,
    ) -> CatalogEntry {
        CatalogEntry {
            dispatcher: dispatcher.to_string(),
            arg: arg.to_string(),
            label: label.to_string(),
            keywords: keywords.into_iter().map(|s| s.to_string()).collect(),
            arg_template: None,
            triggers: Vec::new(),
            layout: None,
        }
    }

    fn make_parameterized_entry(
        dispatcher: &str,
        label: &str,
        template: &str,
        triggers: Vec<&str>,
    ) -> CatalogEntry {
        CatalogEntry {
            dispatcher: dispatcher.to_string(),
            arg: String::new(),
            label: label.to_string(),
            keywords: Vec::new(),
            arg_template: Some(template.to_string()),
            triggers: triggers.into_iter().map(|s| s.to_string()).collect(),
            layout: None,
        }
    }

    #[test]
    fn test_make_dispatch_id() {
        assert_eq!(make_dispatch_id("killactive", ""), "dispatch:killactive");
        assert_eq!(
            make_dispatch_id("movewindow", "l"),
            "dispatch:movewindow:l"
        );
        assert_eq!(
            make_dispatch_id("layoutmsg", "colresize all 0.5"),
            "dispatch:layoutmsg:colresize all 0.5"
        );
        assert_eq!(
            make_dispatch_id("exec", "  some   spaced   arg  "),
            "dispatch:exec:some spaced arg"
        );
    }

    #[test]
    fn test_make_data() {
        assert_eq!(DispatchProvider::make_data("killactive", ""), "killactive");
        assert_eq!(
            DispatchProvider::make_data("movewindow", "l"),
            "movewindow l"
        );
    }

    #[test]
    fn test_commands_from_catalog() {
        let entries = vec![
            make_entry(
                "killactive",
                "",
                "Close active window",
                vec!["close", "kill"],
            ),
            make_entry("movewindow", "l", "Move window left", vec!["move", "left"]),
        ];
        let provider = DispatchProvider::new(entries);
        let commands = provider.commands();

        assert_eq!(commands.len(), 2);
        assert_eq!(commands[0].id, "dispatch:killactive");
        assert_eq!(commands[0].label, "Close active window");
        assert_eq!(commands[0].provider, "dispatch");
        assert_eq!(commands[0].data, "killactive");
        assert_eq!(commands[1].id, "dispatch:movewindow:l");
        assert_eq!(commands[1].data, "movewindow l");
    }

    #[test]
    fn test_parameterized_excluded_from_commands() {
        let entries = vec![
            make_entry("killactive", "", "Close", vec![]),
            make_parameterized_entry(
                "renameworkspace",
                "Rename workspace",
                "{active_workspace} {input}",
                vec!["rw"],
            ),
        ];
        let provider = DispatchProvider::new(entries);
        let commands = provider.commands();

        assert_eq!(commands.len(), 1);
        assert_eq!(commands[0].id, "dispatch:killactive");
    }

    #[test]
    fn test_query_commands_trigger_match() {
        let entries = vec![make_parameterized_entry(
            "renameworkspace",
            "Rename workspace",
            "{input}",
            vec!["rw", "rename"],
        )];
        let provider = DispatchProvider::new(entries);
        let results = provider.query_commands("rw awesome");

        assert_eq!(results.len(), 1);
        assert!(results[0].label.contains("awesome"));
        assert!(results[0].data.starts_with("renameworkspace"));
    }

    #[test]
    fn test_query_commands_no_match() {
        let entries = vec![make_parameterized_entry(
            "renameworkspace",
            "Rename",
            "{input}",
            vec!["rw"],
        )];
        let provider = DispatchProvider::new(entries);
        let results = provider.query_commands("something random");
        assert!(results.is_empty());
    }

    #[test]
    fn test_query_commands_trigger_only_no_input() {
        let entries = vec![make_parameterized_entry(
            "renameworkspace",
            "Rename",
            "{input}",
            vec!["rw"],
        )];
        let provider = DispatchProvider::new(entries);
        let results = provider.query_commands("rw ");
        assert!(results.is_empty());
    }

    #[test]
    fn test_resolve_template_input_only() {
        let result = DispatchProvider::resolve_template("{input}", "hello");
        assert_eq!(result, "hello");
    }

    #[test]
    fn test_keywords_include_dispatcher() {
        let entries = vec![make_entry(
            "killactive",
            "",
            "Close window",
            vec!["close"],
        )];
        let provider = DispatchProvider::new(entries);
        let commands = provider.commands();

        assert!(commands[0].keywords.contains(&"killactive".to_string()));
        assert!(commands[0].keywords.contains(&"close".to_string()));
    }
}
