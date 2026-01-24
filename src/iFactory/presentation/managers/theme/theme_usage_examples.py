"""
Theme Usage Examples - How to use the Design System.

This file provides comprehensive examples of using the theme system
in various scenarios throughout the application.
"""

from PySide6.QtWidgets import QApplication, QWidget, QVBoxLayout, QPushButton, QLabel
from PySide6.QtCore import QSize

from iFactory.presentation.managers.theme import (
    ThemeManager,
    DesignTokens,
    ThemeMode,
    IconManager,
    IconSize,
)


def example_basic_usage():
    """Basic theme manager usage."""
    theme_manager = ThemeManager()

    # Get stylesheet
    stylesheet = theme_manager.get_stylesheet()
    QApplication.instance().setStyleSheet(stylesheet)

    # Switch theme
    theme_manager.set_theme("dark")

    # Get design token values
    primary_color = theme_manager.get_color("primary")
    spacing_md = theme_manager.get_spacing("md")

    print(f"Primary color: {primary_color}")
    print(f"Medium spacing: {spacing_md}px")


def example_widget_styling():
    """Styling widgets with theme tokens (NO hardcoded values)."""
    theme_manager = ThemeManager()

    class MyWidget(QWidget):
        def __init__(self, theme_manager: ThemeManager):
            super().__init__()
            self._theme = theme_manager

            # Create layout
            layout = QVBoxLayout(self)

            # Button - NO hardcoded colors!
            button = QPushButton("Click Me")
            button.setStyleSheet(self._theme.get_stylesheet())

            # Label with themed color
            label = QLabel("Themed Text")
            label.setStyleSheet(f"""
                color: {self._theme.get_color('text-primary')};
                font-size: {self._theme.get_typography('body')['font_size']}px;
            """)

            # Card with themed background and border
            card = QWidget()
            card.setProperty("frameType", "card")
            card.setStyleSheet(self._theme.get_stylesheet())

            layout.addWidget(button)
            layout.addWidget(label)
            layout.addWidget(card)


def example_icon_usage():
    """Using icon manager."""
    icon_manager = IconManager()

    # Get icon
    icon = icon_manager.get_icon("dashboard")

    # Get themed icon
    dark_icon = icon_manager.get_icon("dashboard", theme="dark")

    # Get specific size
    large_icon = icon_manager.get_icon("dashboard", size=IconSize.LG)

    # Get all icons in category
    navigation_icons = icon_manager.get_icons_by_category(IconCategory.NAVIGATION)

    # Use in button
    button = QPushButton("Dashboard")
    button.setIcon(icon)
    button.setIconSize(QSize(24, 24))


def example_custom_stylesheet():
    """Creating custom stylesheet using design tokens."""
    theme_manager = ThemeManager()

    # Get current theme mode
    mode = theme_manager.mode

    # Build custom stylesheet using design tokens
    custom_qss = f"""
    QWidget {{
        background-color: {theme_manager.get_color('background', mode)};
        color: {theme_manager.get_color('text-primary', mode)};
    }}

    QPushButton {{
        background-color: {theme_manager.get_color('primary', mode)};
        color: {theme_manager.get_color('background', mode)};
        border: none;
        border-radius: {theme_manager.get_radius('md')}px;
        padding: {theme_manager.get_spacing('sm')}px {theme_manager.get_spacing('md')}px;
        font-size: {theme_manager.get_typography('body')['font_size']}px;
    }}

    QPushButton:hover {{
        background-color: {theme_manager.get_color('primary-hover', mode)};
    }}

    QPushButton:pressed {{
        background-color: {theme_manager.get_color('primary-active', mode)};
    }}

    QFrame[frameType="card"] {{
        background-color: {theme_manager.get_color('surface', mode)};
        border: 1px solid {theme_manager.get_color('border', mode)};
        border-radius: {theme_manager.get_radius('lg')}px;
        box-shadow: {theme_manager.get_shadow('md', mode)};
    }}
    """

    return custom_qss


def example_theme_switching():
    """Implementing theme switching in application."""
    theme_manager = ThemeManager()

    class MainWindow(QWidget):
        def __init__(self, theme_manager: ThemeManager):
            super().__init__()
            self._theme = theme_manager

            # Create theme toggle button
            self.theme_toggle = QPushButton("Toggle Theme")
            self.theme_toggle.clicked.connect(self._toggle_theme)

            # Listen to theme changes
            self._theme.theme_changed.connect(self._on_theme_changed)

        def _toggle_theme(self):
            """Toggle between light and dark theme."""
            new_mode = "dark" if self._theme.mode == ThemeMode.LIGHT else "light"
            self._theme.set_theme(new_mode)

        def _on_theme_changed(self, mode: str):
            """Handle theme change."""
            # Reapply stylesheet
            self._theme.apply_stylesheet(QApplication.instance())
            print(f"Theme changed to: {mode}")


def example_status_indicators():
    """Using status colors for device indicators."""
    theme_manager = ThemeManager()

    def get_status_indicator(status_code: str) -> str:
        """Get color for device status."""
        status_map = {
            "1": "status-running",
            "2": "status-shutdown",
            "3": "status-stop",
            "4": "status-maintenance",
            "5": "status-alarm",
            "0": "status-unknown",
        }

        status_key = status_map.get(status_code, "status-unknown")
        return theme_manager.get_color(status_key)

    # Create status label
    status_label = QLabel("Device Status: Running")
    status_color = get_status_indicator("1")
    status_label.setStyleSheet(f"color: {status_color}; font-weight: bold;")


def example_responsive_spacing():
    """Using design tokens for responsive layouts."""
    theme_manager = ThemeManager()

    # Define spacing scale
    spacing = {
        "mobile": {
            "sm": theme_manager.get_spacing("xs"),
            "md": theme_manager.get_spacing("sm"),
            "lg": theme_manager.get_spacing("md"),
        },
        "desktop": {
            "sm": theme_manager.get_spacing("sm"),
            "md": theme_manager.get_spacing("md"),
            "lg": theme_manager.get_spacing("lg"),
        },
    }

    def get_spacing(size: str, context: str = "desktop") -> int:
        """Get spacing value for size and context."""
        return spacing.get(context, spacing["desktop"]).get(size, 0)


def example_typography_system():
    """Using typography tokens for consistent text sizing."""
    theme_manager = ThemeManager()

    # Get typography settings
    body_typo = theme_manager.get_typography("body")
    heading_typo = theme_manager.get_typography("heading")

    # Apply to label
    body_label = QLabel("Body text")
    body_label.setStyleSheet(f"""
        font-family: {body_typo['font_family']};
        font-size: {body_typo['font_size']}px;
        font-weight: {body_typo['font_weight']};
        line-height: {body_typo['line_height']};
    """)

    heading_label = QLabel("Heading")
    heading_label.setStyleSheet(f"""
        font-family: {heading_typo['font_family']};
        font-size: {heading_typo['font_size']}px;
        font-weight: {heading_typo['font_weight']};
        line-height: {heading_typo['line_height']};
    """)


def example_custom_component():
    """Creating custom component with design system."""
    theme_manager = ThemeManager()

    class MetricCard(QWidget):
        """Custom metric card using design tokens."""

        def __init__(self, title: str, value: str, theme_manager: ThemeManager):
            super().__init__()
            self._theme = theme_manager

            # Apply design system styling
            self.setProperty("frameType", "card")

            # Create UI
            layout = QVBoxLayout(self)
            layout.setSpacing(self._theme.get_spacing("sm"))
            layout.setContentsMargins(
                self._theme.get_spacing("md"),
                self._theme.get_spacing("md"),
                self._theme.get_spacing("md"),
                self._theme.get_spacing("md"),
            )

            # Title label
            title_label = QLabel(title)
            title_label.setStyleSheet(f"""
                font-size: {self._theme.get_typography('body-small')['font_size']}px;
                color: {self._theme.get_color('text-secondary')};
                font-weight: {self._theme.get_typography('body-small')['font_weight']};
            """)

            # Value label
            value_label = QLabel(value)
            value_label.setStyleSheet(f"""
                font-size: {self._theme.get_typography('display-small')['font_size']}px;
                color: {self._theme.get_color('text-primary')};
                font-weight: {self._theme.get_typography('display-small')['font_weight']};
            """)

            layout.addWidget(title_label)
            layout.addWidget(value_label)


def example_theme_export():
    """Exporting theme configuration."""
    theme_manager = ThemeManager()

    # Export current theme to JSON
    theme_manager.export_theme_config("theme_export.json")

    # Result: JSON file with all design tokens and current theme mode


if __name__ == "__main__":
    # Run examples
    print("=== Design System Examples ===\n")

    print("1. Basic Usage:")
    example_basic_usage()

    print("\n2. Custom Stylesheet:")
    custom_stylesheet = example_custom_stylesheet()
    print(f"Generated {len(custom_stylesheet)} characters of QSS")

    print("\n3. Status Indicators:")
    running_color = example_status_indicators()
    print(f"Running status color: {running_color}")

    print("\n4. Responsive Spacing:")
    spacing_md = example_responsive_spacing()
    print(f"Desktop medium spacing: {spacing_md}px")

    print("\n5. Typography System:")
    example_typography_system()

    print("\n=== All examples completed ===")
