use std::collections::HashMap;

use nucleo_matcher::pattern::{CaseMatching, Normalization, Pattern};
use nucleo_matcher::{Config, Matcher, Utf32Str};

use crate::providers::Command;
use crate::store::Store;

/// A scored command ready for display.
#[derive(Debug, Clone)]
pub struct ScoredCommand {
    pub command: Command,
    pub score: f64,
}

/// The search/ranking engine. Combines nucleo fuzzy matching with frecency.
pub struct Engine {
    frecency_weight: f64,
    aliases: HashMap<String, String>,
}

impl Engine {
    pub fn new(frecency_weight: f64, aliases: HashMap<String, String>) -> Self {
        Self {
            frecency_weight,
            aliases,
        }
    }

    /// Rank commands for an empty query: pure frecency order, showing the
    /// user's most-used commands. If no history exists, return all commands
    /// in their original order.
    pub fn rank_empty_query(
        &self,
        commands: &[Command],
        store: &Store,
        max_results: usize,
    ) -> Vec<ScoredCommand> {
        let top = store.top_global(max_results);

        if top.is_empty() {
            // No history yet — show first N commands as-is.
            return commands
                .iter()
                .take(max_results)
                .map(|c| ScoredCommand {
                    command: c.clone(),
                    score: 0.0,
                })
                .collect();
        }

        // Build a lookup from command id → Command
        let by_id: HashMap<&str, &Command> = commands.iter().map(|c| (c.id.as_str(), c)).collect();

        let mut results: Vec<ScoredCommand> = top
            .into_iter()
            .filter_map(|(id, score)| {
                by_id.get(id.as_str()).map(|cmd| ScoredCommand {
                    command: (*cmd).clone(),
                    score,
                })
            })
            .collect();

        // If we don't have enough from history, pad with unscored commands.
        if results.len() < max_results {
            let seen: std::collections::HashSet<String> =
                results.iter().map(|r| r.command.id.clone()).collect();
            for cmd in commands {
                if results.len() >= max_results {
                    break;
                }
                if !seen.contains(&cmd.id) {
                    results.push(ScoredCommand {
                        command: cmd.clone(),
                        score: 0.0,
                    });
                }
            }
        }

        results
    }

    /// Rank commands for a non-empty query: fuzzy match + frecency boost.
    ///
    /// If the query matches an alias exactly, that command is pinned to #1.
    pub fn rank_query(
        &self,
        query: &str,
        commands: &[Command],
        store: &Store,
        max_results: usize,
    ) -> Vec<ScoredCommand> {
        let normalized_query = query.trim().to_lowercase();

        // Check for alias match.
        let alias_target = self.aliases.get(&normalized_query).cloned();

        let mut matcher = Matcher::new(Config::DEFAULT);
        let pattern = Pattern::parse(query, CaseMatching::Ignore, Normalization::Smart);

        let mut results: Vec<ScoredCommand> = Vec::new();
        let mut buf = Vec::new();

        for cmd in commands {
            // Try to get a fuzzy score against the label.
            let label_score = {
                buf.clear();
                let haystack = Utf32Str::new(&cmd.label, &mut buf);
                pattern.score(haystack, &mut matcher)
            };

            // Also try keywords — take the best score.
            let keyword_score = cmd.keywords.iter().filter_map(|kw| {
                buf.clear();
                let haystack = Utf32Str::new(kw, &mut buf);
                pattern.score(haystack, &mut matcher)
            }).max();

            // Also try hotkey text.
            let hotkey_score = cmd.hotkey.as_ref().and_then(|hk| {
                buf.clear();
                let haystack = Utf32Str::new(hk, &mut buf);
                pattern.score(haystack, &mut matcher)
            });

            // Take the best fuzzy score across all fields.
            let best_fuzzy = [label_score, keyword_score, hotkey_score]
                .into_iter()
                .flatten()
                .max();

            let Some(fuzzy_score) = best_fuzzy else {
                continue; // No match at all — skip this command.
            };

            // Combine fuzzy score with frecency.
            let global_frec = store.global_score(&cmd.id);
            let query_frec = store.query_score(&normalized_query, &cmd.id);
            // Per-query frecency matters more for mnemonic learning.
            let combined_frec = query_frec * 2.0 + global_frec;

            let final_score = fuzzy_score as f64
                * (1.0 + self.frecency_weight * (combined_frec + 1.0).ln());

            results.push(ScoredCommand {
                command: cmd.clone(),
                score: final_score,
            });
        }

        // Sort by score descending.
        results.sort_by(|a, b| {
            b.score
                .partial_cmp(&a.score)
                .unwrap_or(std::cmp::Ordering::Equal)
        });

        // If there's an alias match, move it to the top.
        if let Some(ref target_id) = alias_target {
            if let Some(pos) = results.iter().position(|r| r.command.id == *target_id) {
                let aliased = results.remove(pos);
                results.insert(0, aliased);
            } else {
                // The alias target isn't in fuzzy results — find it in all
                // commands and insert it at #1 anyway.
                if let Some(cmd) = commands.iter().find(|c| c.id == *target_id) {
                    results.insert(
                        0,
                        ScoredCommand {
                            command: cmd.clone(),
                            score: f64::MAX,
                        },
                    );
                }
            }
        }

        results.truncate(max_results);
        results
    }
}
