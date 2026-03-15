"""
categories.py  —  Category definitions and colour palette
==========================================================
Provides default categories with assigned colours, and helpers
to manage a user-editable category list saved in config.json.
"""

# Default categories shipped with the app
DEFAULT_CATEGORIES = ["General", "Work", "Personal", "Shopping", "Health", "Finance"]

# Colour palette for category badges (cycles through for custom categories)
# Each entry: (background, foreground)
CATEGORY_COLORS_LIGHT = [
    ("#DBEAFE", "#1E40AF"),  # blue    — General
    ("#EDE9FE", "#5B21B6"),  # purple  — Work
    ("#D1FAE5", "#065F46"),  # green   — Personal
    ("#FEF3C7", "#92400E"),  # amber   — Shopping
    ("#FCE7F3", "#9D174D"),  # pink    — Health
    ("#E0F2FE", "#0C4A6E"),  # sky     — Finance
    ("#F3F4F6", "#374151"),  # grey    — overflow
    ("#FFF7ED", "#9A3412"),  # orange
    ("#F0FDF4", "#14532D"),  # emerald
    ("#FDF4FF", "#701A75"),  # fuchsia
]

CATEGORY_COLORS_DARK = [
    ("#1E3A5F", "#93C5FD"),  # blue
    ("#2E1F5E", "#C4B5FD"),  # purple
    ("#14352A", "#6EE7B7"),  # green
    ("#3D2B0A", "#FCD34D"),  # amber
    ("#3D1535", "#F9A8D4"),  # pink
    ("#0A2E3D", "#7DD3FC"),  # sky
    ("#1F2937", "#9CA3AF"),  # grey
    ("#3D1A08", "#FDBA74"),  # orange
    ("#052E16", "#4ADE80"),  # emerald
    ("#2E0A38", "#E879F9"),  # fuchsia
]


def get_color(category: str, categories: list, dark_mode: bool) -> tuple:
    """Return (bg, fg) colour pair for the given category name."""
    palette = CATEGORY_COLORS_DARK if dark_mode else CATEGORY_COLORS_LIGHT
    try:
        idx = categories.index(category) % len(palette)
    except ValueError:
        idx = len(palette) - 1
    return palette[idx]


def load_categories(config: dict) -> list:
    """Extract saved categories from config, filling in defaults if absent."""
    saved = config.get("categories", None)
    if saved and isinstance(saved, list) and len(saved) > 0:
        # Ensure General always exists
        if "General" not in saved:
            saved.insert(0, "General")
        return saved
    return list(DEFAULT_CATEGORIES)