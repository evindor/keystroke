# Keystroke browser-tabs: only the adapters this extension needs are vendored.
from .atspi import AtspiProvider
from .hyprland import HyprlandProvider

__all__ = [
    "AtspiProvider",
    "HyprlandProvider",
]
