use std::cell::{Cell, RefCell};
use std::rc::Rc;

use gdk4;
use gtk4::prelude::*;
use gtk4_layer_shell::{KeyboardMode, Layer, LayerShell};

// ---------------------------------------------------------------------------
// Launcher
// ---------------------------------------------------------------------------

pub struct Launcher {
    pub window: gtk4::ApplicationWindow,
    pub input: gtk4::Entry,
    pub results_box: gtk4::Box,
    pub selected_index: Rc<Cell<i32>>,

    on_execute: Rc<RefCell<Option<Box<dyn Fn(i32)>>>>,
    on_query_changed: Rc<RefCell<Option<Box<dyn Fn(String)>>>>,
    on_dismiss: Rc<RefCell<Option<Box<dyn Fn()>>>>,
}

impl Launcher {
    /// Create the launcher UI. `app` is the GTK Application.
    pub fn new(app: &gtk4::Application, width: i32, max_visible_results: usize) -> Self {
        // --- Callbacks (connected later) ---
        let on_execute: Rc<RefCell<Option<Box<dyn Fn(i32)>>>> = Rc::new(RefCell::new(None));
        let on_query_changed: Rc<RefCell<Option<Box<dyn Fn(String)>>>> =
            Rc::new(RefCell::new(None));
        let on_dismiss: Rc<RefCell<Option<Box<dyn Fn()>>>> = Rc::new(RefCell::new(None));

        // --- Window ---
        let window = gtk4::ApplicationWindow::new(app);
        window.set_default_size(width, -1);

        // Layer shell setup
        window.init_layer_shell();
        window.set_layer(Layer::Overlay);
        window.set_namespace(Some("keystroke"));
        window.set_keyboard_mode(KeyboardMode::Exclusive);
        window.set_exclusive_zone(-1);

        // --- Layout ---

        // Main container (vertical box)
        let container = gtk4::Box::new(gtk4::Orientation::Vertical, 0);
        container.add_css_class("container");
        container.set_width_request(width);

        // Search input
        let input = gtk4::Entry::new();
        input.add_css_class("search-input");
        input.set_placeholder_text(Some("Type a command..."));
        container.append(&input);

        // Separator (thin horizontal line)
        let separator = gtk4::Box::new(gtk4::Orientation::Horizontal, 0);
        separator.add_css_class("separator");
        container.append(&separator);

        // Scrolled window for results
        let scrolled_window = gtk4::ScrolledWindow::new();
        scrolled_window.set_max_content_height((max_visible_results * 44) as i32);
        scrolled_window.set_propagate_natural_height(true);
        scrolled_window.set_hscrollbar_policy(gtk4::PolicyType::Never);

        // Results list
        let results_box = gtk4::Box::new(gtk4::Orientation::Vertical, 0);
        results_box.add_css_class("results-list");
        scrolled_window.set_child(Some(&results_box));

        container.append(&scrolled_window);
        window.set_child(Some(&container));

        // --- Selection state ---
        let selected_index: Rc<Cell<i32>> = Rc::new(Cell::new(0));

        // --- Key handling (on window, CAPTURE phase) ---
        // Must use capture phase so we intercept Enter/Escape/arrows
        // before the Entry widget's built-in handlers consume them.
        let key_controller = gtk4::EventControllerKey::new();
        key_controller.set_propagation_phase(gtk4::PropagationPhase::Capture);

        {
            let window_ref = window.clone();
            let input_ref = input.clone();
            let results_box_ref = results_box.clone();
            let selected_ref = selected_index.clone();
            let on_execute_ref = on_execute.clone();
            let on_dismiss_ref = on_dismiss.clone();

            key_controller.connect_key_pressed(
                move |_ctrl, key, _code, modifier| {
                    let ctrl = modifier.contains(gdk4::ModifierType::CONTROL_MASK);

                    let is_up = key == gdk4::Key::Up
                        || (ctrl && key == gdk4::Key::k)
                        || (ctrl && key == gdk4::Key::p);

                    let is_down = key == gdk4::Key::Down
                        || (ctrl && key == gdk4::Key::j)
                        || (ctrl && key == gdk4::Key::n);

                    if key == gdk4::Key::Escape {
                        // Hide window, clear input
                        input_ref.set_text("");
                        window_ref.set_visible(false);
                        if let Some(ref cb) = *on_dismiss_ref.borrow() {
                            cb();
                        }
                        glib::Propagation::Stop
                    } else if key == gdk4::Key::Return || key == gdk4::Key::KP_Enter {
                        if let Some(ref cb) = *on_execute_ref.borrow() {
                            cb(selected_ref.get());
                        }
                        glib::Propagation::Stop
                    } else if is_up {
                        move_selection(&results_box_ref, &selected_ref, -1);
                        glib::Propagation::Stop
                    } else if is_down {
                        move_selection(&results_box_ref, &selected_ref, 1);
                        glib::Propagation::Stop
                    } else {
                        glib::Propagation::Proceed
                    }
                },
            );
        }

        window.add_controller(key_controller);

        // --- Input text changed ---
        {
            let on_query_changed_ref = on_query_changed.clone();
            input.connect_changed(move |entry| {
                let text = entry.text().to_string();
                if let Some(ref cb) = *on_query_changed_ref.borrow() {
                    cb(text);
                }
            });
        }

        // Don't present yet (initially hidden)

        Self {
            window,
            input,
            results_box,
            selected_index,
            on_execute,
            on_query_changed,
            on_dismiss,
        }
    }

    /// Update the displayed results. Each entry is (label, hotkey_text_or_empty).
    /// Clears previous results and rebuilds the list.
    pub fn set_results(&self, results: &[(String, String)]) {
        // Remove all existing children
        while let Some(child) = self.results_box.first_child() {
            self.results_box.remove(&child);
        }

        // Reset selection to 0
        self.selected_index.set(0);

        for (i, (label, hotkey)) in results.iter().enumerate() {
            let row = gtk4::Box::new(gtk4::Orientation::Horizontal, 0);
            row.add_css_class("result-row");

            // Label (left side)
            let label_widget = gtk4::Label::new(Some(label));
            label_widget.add_css_class("result-label");
            label_widget.set_halign(gtk4::Align::Start);
            label_widget.set_hexpand(true);
            row.append(&label_widget);

            // Hotkey (right side)
            let hotkey_widget = gtk4::Label::new(Some(hotkey));
            hotkey_widget.add_css_class("result-hotkey");
            hotkey_widget.set_halign(gtk4::Align::End);
            row.append(&hotkey_widget);

            // Mark first row as selected
            if i == 0 {
                row.add_css_class("selected");
            }

            self.results_box.append(&row);
        }
    }

    /// Show the overlay, focus the input.
    pub fn show(&self) {
        self.window.present();
        self.input.grab_focus();
    }

    /// Hide the overlay, clear input and results.
    pub fn hide(&self) {
        self.input.set_text("");
        self.selected_index.set(0);
        // Clear results
        while let Some(child) = self.results_box.first_child() {
            self.results_box.remove(&child);
        }
        self.window.set_visible(false);
    }

    /// Connect a callback for when Enter is pressed (command execution).
    /// The callback receives the selected index.
    pub fn connect_execute<F: Fn(i32) + 'static>(&self, f: F) {
        *self.on_execute.borrow_mut() = Some(Box::new(f));
    }

    /// Connect a callback for when the input text changes.
    pub fn connect_query_changed<F: Fn(String) + 'static>(&self, f: F) {
        *self.on_query_changed.borrow_mut() = Some(Box::new(f));
    }

    /// Connect a callback for when Escape is pressed.
    pub fn connect_dismiss<F: Fn() + 'static>(&self, f: F) {
        *self.on_dismiss.borrow_mut() = Some(Box::new(f));
    }

    /// Clear the input text.
    pub fn clear_input(&self) {
        self.input.set_text("");
    }

    /// Set the selected index and update CSS classes.
    pub fn set_selected(&self, index: i32) {
        let old = self.selected_index.get();
        if let Some(old_widget) = nth_child(&self.results_box, old) {
            old_widget.remove_css_class("selected");
        }
        self.selected_index.set(index);
        if let Some(new_widget) = nth_child(&self.results_box, index) {
            new_widget.add_css_class("selected");
        }
    }

    /// Focus the input entry.
    pub fn focus_input(&self) {
        self.input.grab_focus();
    }

    /// Check if the window is currently visible.
    pub fn is_visible(&self) -> bool {
        self.window.is_visible()
    }

    /// Get the current query text.
    pub fn get_query(&self) -> String {
        self.input.text().to_string()
    }
}

// ---------------------------------------------------------------------------
// Selection helpers
// ---------------------------------------------------------------------------

/// Count the number of child widgets in a GTK Box.
fn child_count(container: &gtk4::Box) -> i32 {
    let mut count = 0i32;
    let mut child = container.first_child();
    while let Some(c) = child {
        count += 1;
        child = c.next_sibling();
    }
    count
}

/// Get the nth child widget from a GTK Box (0-indexed).
fn nth_child(container: &gtk4::Box, n: i32) -> Option<gtk4::Widget> {
    let mut idx = 0i32;
    let mut child = container.first_child();
    while let Some(c) = child {
        if idx == n {
            return Some(c);
        }
        idx += 1;
        child = c.next_sibling();
    }
    None
}

/// Move the selection by `delta` (-1 for up, +1 for down), wrapping around.
fn move_selection(results_box: &gtk4::Box, selected_index: &Rc<Cell<i32>>, delta: i32) {
    let total = child_count(results_box);
    if total == 0 {
        return;
    }

    let old = selected_index.get();

    // Remove "selected" from old row
    if let Some(old_widget) = nth_child(results_box, old) {
        old_widget.remove_css_class("selected");
    }

    // Compute new index with wrapping
    let mut new = old + delta;
    if new < 0 {
        new = total - 1;
    } else if new >= total {
        new = 0;
    }

    // Add "selected" to new row
    if let Some(new_widget) = nth_child(results_box, new) {
        new_widget.add_css_class("selected");
    }

    selected_index.set(new);
}
