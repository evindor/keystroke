pub mod calculator;
pub mod hyprland;

/// A command that can be executed by the launcher.
#[derive(Debug, Clone)]
pub struct Command {
    /// Unique identifier: "hyprland:killactive", "hyprland:exec:omarchy-launch-browser"
    pub id: String,
    /// Primary display text: "Close window"
    pub label: String,
    /// Extra searchable terms
    pub keywords: Vec<String>,
    /// Human-readable hotkey: "SUPER + W"
    pub hotkey: Option<String>,
    /// Which provider owns this command
    pub provider: String,
    /// Provider-specific execution data (e.g., "killactive " or "exec omarchy-launch-browser")
    pub data: String,
}

/// Trait for command providers. Each provider fetches commands from a source
/// and knows how to execute them.
pub trait Provider {
    /// Unique provider identifier
    fn id(&self) -> &str;
    /// Fetch all available commands (may do I/O). Called once on show.
    fn commands(&self) -> Vec<Command>;
    /// Execute a command by its provider-specific data
    fn execute(&self, command: &Command);
    /// Generate dynamic commands based on the current query.
    /// Default: no dynamic commands. Override for providers like calculator.
    fn query_commands(&self, _query: &str) -> Vec<Command> {
        Vec::new()
    }
}
