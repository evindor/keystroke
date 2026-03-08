mod config;
mod engine;
mod providers;
mod store;
mod theme;
mod ui;

use std::cell::{Cell, RefCell};
use std::rc::Rc;

use gdk4;
use gio;
use gio::prelude::*;
use gtk4;

use config::Config;
use engine::{Engine, ScoredCommand};
use providers::{Command, Provider};
use store::Store;
use theme::Theme;
use ui::DisplayRow;

// Keep the file monitor alive so the signal stays connected.
#[allow(dead_code)]
struct CssMonitor(gio::FileMonitor);

// ---------------------------------------------------------------------------
// Application state (single-threaded, shared via Rc<RefCell<...>>)
// ---------------------------------------------------------------------------

#[allow(dead_code)] // user_css + _css_monitor kept alive for GTK provider lifetime
struct AppState {
    commands: Vec<Command>,
    config: Config,
    store: Store,
    engine: Engine,
    providers: Vec<Box<dyn Provider>>,
    base_css: gtk4::CssProvider,
    user_css: gtk4::CssProvider,
    _css_monitor: Option<CssMonitor>,
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/// Collect commands from every active provider.
fn fetch_all_commands(providers: &[Box<dyn Provider>]) -> Vec<Command> {
    providers.iter().flat_map(|p| p.commands()).collect()
}

/// Build the list of active providers from the current config.
fn build_providers(config: &Config) -> Vec<Box<dyn Provider>> {
    let mut active: Vec<Box<dyn Provider>> = Vec::new();
    if config.providers.dispatches {
        let entries = config.load_catalog();
        let dp = providers::hyprland::DispatchProvider::new(entries);
        active.push(Box::new(dp));
    }
    // Apps provider (desktop entries).
    active.push(Box::new(providers::apps::AppsProvider::new()));
    // Calculator is always available.
    active.push(Box::new(providers::calculator::CalculatorProvider::new()));
    active
}

/// Convert a slice of `ScoredCommand` into display rows for the UI.
fn scored_to_display(scored: &[ScoredCommand]) -> Vec<DisplayRow> {
    scored
        .iter()
        .map(|sc| DisplayRow {
            label: sc.command.label.clone(),
            hotkey: sc.command.hotkey.clone().unwrap_or_default(),
            icon: sc.command.icon.clone(),
        })
        .collect()
}

/// Load theme-derived CSS into an existing provider.
fn load_base_css(provider: &gtk4::CssProvider, config: &Config) {
    let theme = Theme::load();
    let css_string = theme.generate_css(
        config.appearance.border_radius,
        config.appearance.width,
    );
    provider.load_from_data(&css_string);
}

/// Load user CSS into an existing provider (clears if file is absent).
fn load_user_css(provider: &gtk4::CssProvider) {
    let css = theme::load_user_css().unwrap_or_default();
    provider.load_from_data(&css);
}

/// Set up a `gio::FileMonitor` on the user CSS file.  Returns `None` if the
/// path cannot be resolved.
fn setup_css_monitor(user_provider: &gtk4::CssProvider) -> Option<CssMonitor> {
    let path = theme::user_css_path()?;
    let file = gio::File::for_path(&path);
    let monitor = file.monitor_file(gio::FileMonitorFlags::NONE, gio::Cancellable::NONE).ok()?;

    let provider = user_provider.clone();
    monitor.connect_changed(move |_monitor, _file, _other, event| {
        use gio::FileMonitorEvent::*;
        match event {
            Changed | Created | Deleted | MovedIn | MovedOut => {
                load_user_css(&provider);
            }
            _ => {}
        }
    });

    Some(CssMonitor(monitor))
}

// ---------------------------------------------------------------------------
// Show / hide helpers
// ---------------------------------------------------------------------------

/// Perform all actions needed when the launcher becomes visible.
fn on_show(
    state: &Rc<RefCell<Option<AppState>>>,
    launcher: &Rc<RefCell<Option<ui::Launcher>>>,
) {
    let mut st_opt = state.borrow_mut();
    let Some(ref mut st) = *st_opt else { return };

    // Reload config (in case it changed on disk).
    st.config = Config::load();

    // Reload base CSS (theme may have changed).
    load_base_css(&st.base_css, &st.config);

    // Rebuild engine with potentially-updated config.
    st.engine = Engine::new(
        st.config.scoring.frecency_weight,
        st.config.aliases.clone(),
    );

    // Rebuild providers from config.
    st.providers = build_providers(&st.config);

    // Refresh commands from providers.
    st.commands = fetch_all_commands(&st.providers);

    // Reload store from disk (picks up changes from other sessions).
    st.store = Store::load(st.config.scoring.half_life_days * 86400.0);

    // Rank with empty query (frecency order).
    let max_results = st.config.appearance.max_visible_results;
    let scored = st.engine.rank_empty_query(&st.commands, &st.store, max_results);
    let display = scored_to_display(&scored);

    // Must drop the state borrow before touching launcher.
    drop(st_opt);

    // Update the UI.
    if let Some(ref l) = *launcher.borrow() {
        l.set_results(&display);
        l.clear_input();
        l.set_selected(0);
        l.focus_input();
        l.show();
    }
}

/// Hide the launcher and reset UI state.
fn on_hide(launcher: &Rc<RefCell<Option<ui::Launcher>>>) {
    if let Some(ref l) = *launcher.borrow() {
        l.hide();
    }
}

// ---------------------------------------------------------------------------
// Main
// ---------------------------------------------------------------------------

fn main() {
    let app = gtk4::Application::new(
        Some("com.keystroke.launcher"),
        gio::ApplicationFlags::HANDLES_COMMAND_LINE,
    );

    // The command-line handler is required for the GApplication daemon pattern.
    // When a second instance is launched, this handler fires on the *primary*
    // instance.  We simply call activate() to toggle visibility.
    app.connect_command_line(|app, _| {
        app.activate();
        0.into()
    });

    // Shared state wrapped for single-threaded GTK callbacks.
    let state: Rc<RefCell<Option<AppState>>> = Rc::new(RefCell::new(None));
    let launcher: Rc<RefCell<Option<ui::Launcher>>> = Rc::new(RefCell::new(None));
    let initialized = Rc::new(Cell::new(false));

    // Current ranked results (kept in sync with the UI list so we can look up
    // the Command at the selected index when the user executes).
    let current_scored: Rc<RefCell<Vec<ScoredCommand>>> = Rc::new(RefCell::new(Vec::new()));

    app.connect_activate({
        let state = Rc::clone(&state);
        let launcher = Rc::clone(&launcher);
        let initialized = Rc::clone(&initialized);
        let current_scored = Rc::clone(&current_scored);

        move |app| {
            if !initialized.get() {
                // -------------------------------------------------------
                // First activation: build everything
                // -------------------------------------------------------
                initialized.set(true);

                // Load config.
                let config = Config::load();

                // --- CSS: two-layer setup ---
                let display = gdk4::Display::default().unwrap();

                let base_css = gtk4::CssProvider::new();
                load_base_css(&base_css, &config);
                gtk4::style_context_add_provider_for_display(
                    &display,
                    &base_css,
                    gtk4::STYLE_PROVIDER_PRIORITY_APPLICATION,
                );

                let user_css = gtk4::CssProvider::new();
                theme::ensure_default_user_css();
                load_user_css(&user_css);
                gtk4::style_context_add_provider_for_display(
                    &display,
                    &user_css,
                    gtk4::STYLE_PROVIDER_PRIORITY_USER,
                );

                let css_monitor = setup_css_monitor(&user_css);

                // Set up engine.
                let engine_inst = Engine::new(
                    config.scoring.frecency_weight,
                    config.aliases.clone(),
                );

                // Set up providers.
                let active_providers = build_providers(&config);

                // Fetch initial commands.
                let commands = fetch_all_commands(&active_providers);

                // Load store.
                let store_inst = Store::load(config.scoring.half_life_days * 86400.0);

                // Build initial results (empty query = frecency).
                let max_results = config.appearance.max_visible_results;
                let scored = engine_inst.rank_empty_query(&commands, &store_inst, max_results);
                *current_scored.borrow_mut() = scored.clone();

                let display = scored_to_display(&scored);

                // Build the UI.
                let l = ui::Launcher::new(
                    app,
                    config.appearance.width as i32,
                    config.appearance.max_visible_results,
                );

                // Set initial results.
                l.set_results(&display);
                l.set_selected(0);

                // --- Connect: on query changed ---
                {
                    let state = Rc::clone(&state);
                    let launcher = Rc::clone(&launcher);
                    let current_scored = Rc::clone(&current_scored);

                    l.connect_query_changed(move |query| {
                        let st = state.borrow();
                        let Some(ref st) = *st else { return };

                        let max_results = st.config.appearance.max_visible_results;

                        let scored = if query.is_empty() {
                            st.engine.rank_empty_query(
                                &st.commands,
                                &st.store,
                                max_results,
                            )
                        } else {
                            st.engine.rank_query(
                                &query,
                                &st.commands,
                                &st.providers,
                                &st.store,
                                max_results,
                            )
                        };

                        let display = scored_to_display(&scored);
                        *current_scored.borrow_mut() = scored;

                        if let Some(ref l) = *launcher.borrow() {
                            l.set_results(&display);
                            l.set_selected(0);
                        }
                    });
                }

                // --- Connect: on execute ---
                {
                    let state = Rc::clone(&state);
                    let launcher = Rc::clone(&launcher);
                    let current_scored = Rc::clone(&current_scored);

                    l.connect_execute(move |index| {
                        let scored = current_scored.borrow();
                        let Some(sc) = scored.get(index as usize) else {
                            return;
                        };
                        let command = sc.command.clone();
                        drop(scored);

                        // Grab query before borrowing state mutably.
                        let query = {
                            let l_ref = launcher.borrow();
                            l_ref.as_ref().map(|l| l.get_query()).unwrap_or_default()
                        };

                        {
                            let mut st_opt = state.borrow_mut();
                            if let Some(ref mut st) = *st_opt {
                                // Find the owning provider and execute.
                                for provider in &st.providers {
                                    if provider.id() == command.provider {
                                        provider.execute(&command);
                                        break;
                                    }
                                }

                                // Record in store.
                                st.store.record(&query, &command.id);
                                st.store.save();
                            }
                        } // state borrow dropped here

                        // Hide the launcher.
                        if let Some(ref l) = *launcher.borrow() {
                            l.hide();
                        }
                    });
                }

                // --- Connect: on dismiss (Escape) ---
                {
                    let launcher = Rc::clone(&launcher);

                    l.connect_dismiss(move || {
                        if let Some(ref l) = *launcher.borrow() {
                            l.clear_input();
                            l.set_selected(0);
                            l.hide();
                        }
                    });
                }

                // Store state.
                *state.borrow_mut() = Some(AppState {
                    commands,
                    config,
                    store: store_inst,
                    engine: engine_inst,
                    providers: active_providers,
                    base_css,
                    user_css,
                    _css_monitor: css_monitor,
                });

                // Store launcher reference.
                *launcher.borrow_mut() = Some(l);

                // Show on first activation.
                if let Some(ref l) = *launcher.borrow() {
                    l.focus_input();
                    l.show();
                }
            } else {
                // -------------------------------------------------------
                // Subsequent activations: toggle visibility
                // -------------------------------------------------------
                let is_visible = launcher
                    .borrow()
                    .as_ref()
                    .map(|l| l.is_visible())
                    .unwrap_or(false);

                if is_visible {
                    on_hide(&launcher);
                } else {
                    on_show(&state, &launcher);

                    // Refresh the current_scored to match what on_show displayed.
                    let st = state.borrow();
                    if let Some(ref st) = *st {
                        let max = st.config.appearance.max_visible_results;
                        let scored =
                            st.engine.rank_empty_query(&st.commands, &st.store, max);
                        *current_scored.borrow_mut() = scored;
                    }
                }
            }
        }
    });

    app.run();
}
