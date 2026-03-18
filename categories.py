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


def auto_fg(bg_hex: str) -> str:
    """Return black or white foreground that contrasts best with bg_hex."""
    bg_hex = bg_hex.lstrip("#")
    r, g, b = int(bg_hex[0:2], 16), int(bg_hex[2:4], 16), int(bg_hex[4:6], 16)
    # Perceived luminance (ITU-R BT.709)
    luminance = (0.2126 * r + 0.7152 * g + 0.0722 * b) / 255
    return "#1C1917" if luminance > 0.45 else "#F5F5F4"


def get_color(category: str, categories: list, dark_mode: bool,
              custom_colors: dict | None = None) -> tuple:
    """Return (bg, fg) colour pair for the given category name.

    custom_colors: optional dict  {name: {"light": (bg, fg), "dark": (bg, fg)}}
    """
    if custom_colors and category in custom_colors:
        key = "dark" if dark_mode else "light"
        entry = custom_colors[category]
        if key in entry:
            return entry[key]
    palette = CATEGORY_COLORS_DARK if dark_mode else CATEGORY_COLORS_LIGHT
    try:
        idx = categories.index(category) % len(palette)
    except ValueError:
        idx = len(palette) - 1
    return palette[idx]


def load_category_colors(config: dict) -> dict:
    """Load custom per-category colours from config."""
    raw = config.get("category_colors", {})
    result = {}
    for name, entry in raw.items():
        result[name] = {}
        if "light" in entry:
            result[name]["light"] = tuple(entry["light"])
        if "dark" in entry:
            result[name]["dark"] = tuple(entry["dark"])
    return result


def load_categories(config: dict) -> list:
    """Extract saved categories from config, filling in defaults if absent."""
    saved = config.get("categories", None)
    if saved and isinstance(saved, list) and len(saved) > 0:
        # Ensure General always exists
        if "General" not in saved:
            saved.insert(0, "General")
        return saved
    return list(DEFAULT_CATEGORIES)