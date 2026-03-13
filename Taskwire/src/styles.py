"""
This module defines the ModernTheme class for consistent styling across the application.
It provides color palettes and a stylesheet generator for PyQt6 widgets.
"""

class DarkPalette:
    APP_BACKGROUND = "#121212"
    WIDGET_BACKGROUND = "#1e1e2e"
    TEXT_PRIMARY = "#ffffff"
    TEXT_SECONDARY = "#a0a0a0"
    
    ACCENT_RED = "#ff5555"
    ACCENT_GREEN = "#50fa7b"
    ACCENT_BLUE = "#6272a4"
    ACCENT_CYAN = "#8be9fd"
    ACCENT_PURPLE = "#bd93f9"
    ACCENT_ORANGE = "#ffb86c"
    ACCENT_YELLOW = "#f1fa8c"

    BORDER_COLOR = "#44475a"
    ALTERNATE_TABLE_BG = "#2a2a3a"

class LightPalette:
    APP_BACKGROUND = "#f5f6fa"
    WIDGET_BACKGROUND = "#ffffff"
    TEXT_PRIMARY = "#2f3640"
    TEXT_SECONDARY = "#718093"
    
    # Slightly darker accents for better visibility on white
    ACCENT_RED = "#e84118"
    ACCENT_GREEN = "#44bd32"
    ACCENT_BLUE = "#273c75"
    ACCENT_CYAN = "#0097e6"
    ACCENT_PURPLE = "#8c7ae6"
    ACCENT_ORANGE = "#e1b12c"
    ACCENT_YELLOW = "#fbc531"

    BORDER_COLOR = "#dcdde1"
    ALTERNATE_TABLE_BG = "#f1f2f6"

class ModernTheme: # pylint: disable=R0903
    """
    Defines the color palette and provides a static method to generate
    the application's QSS (Qt Style Sheet) for a consistent look and feel.
    """
    # Current Palette (Default to Dark)
    APP_BACKGROUND = DarkPalette.APP_BACKGROUND
    WIDGET_BACKGROUND = DarkPalette.WIDGET_BACKGROUND
    TEXT_PRIMARY = DarkPalette.TEXT_PRIMARY
    TEXT_SECONDARY = DarkPalette.TEXT_SECONDARY
    
    ACCENT_RED = DarkPalette.ACCENT_RED
    ACCENT_GREEN = DarkPalette.ACCENT_GREEN
    ACCENT_BLUE = DarkPalette.ACCENT_BLUE
    ACCENT_CYAN = DarkPalette.ACCENT_CYAN
    ACCENT_PURPLE = DarkPalette.ACCENT_PURPLE
    ACCENT_ORANGE = DarkPalette.ACCENT_ORANGE
    ACCENT_YELLOW = DarkPalette.ACCENT_YELLOW

    BORDER_COLOR = DarkPalette.BORDER_COLOR
    ALTERNATE_TABLE_BG = DarkPalette.ALTERNATE_TABLE_BG

    @classmethod
    def set_theme(cls, mode="dark"):
        """
        Switches the application theme between 'light' and 'dark'.
        Updates the class attributes to match the selected palette.
        """
        palette = LightPalette if mode == "light" else DarkPalette
        
        cls.APP_BACKGROUND = palette.APP_BACKGROUND
        cls.WIDGET_BACKGROUND = palette.WIDGET_BACKGROUND
        cls.TEXT_PRIMARY = palette.TEXT_PRIMARY
        cls.TEXT_SECONDARY = palette.TEXT_SECONDARY
        
        cls.ACCENT_RED = palette.ACCENT_RED
        cls.ACCENT_GREEN = palette.ACCENT_GREEN
        cls.ACCENT_BLUE = palette.ACCENT_BLUE
        cls.ACCENT_CYAN = palette.ACCENT_CYAN
        cls.ACCENT_PURPLE = palette.ACCENT_PURPLE
        cls.ACCENT_ORANGE = palette.ACCENT_ORANGE
        cls.ACCENT_YELLOW = palette.ACCENT_YELLOW

        cls.BORDER_COLOR = palette.BORDER_COLOR
        cls.ALTERNATE_TABLE_BG = palette.ALTERNATE_TABLE_BG

    @staticmethod
    def get_stylesheet():
        """
        Generates and returns the QSS stylesheet string for the application.
        """
        return f"""
        QMainWindow {{
            background-color: {ModernTheme.APP_BACKGROUND};
        }}
        
        QWidget {{
            background-color: {ModernTheme.APP_BACKGROUND};
            color: {ModernTheme.TEXT_PRIMARY};
            font-family: 'Segoe UI', 'Roboto', 'Ubuntu', sans-serif;
            font-size: 14px;
        }}
        
        /* Specific Styles for Cards */
        QFrame.card {{
            background-color: {ModernTheme.WIDGET_BACKGROUND};
            border: 1px solid {ModernTheme.BORDER_COLOR};
            border-radius: 10px;
        }}
        
        QLabel {{
            background-color: transparent;
            border: none;
        }}
        
        QLabel.title {{
            font-size: 16px;
            font-weight: bold;
            color: {ModernTheme.TEXT_SECONDARY};
        }}
        
        QLabel.value {{
            font-size: 24px;
            font-weight: bold;
            color: {ModernTheme.TEXT_PRIMARY};
        }}

        /* ProgressBar Styling */
        QProgressBar {{
            border: 1px solid {ModernTheme.BORDER_COLOR};
            border-radius: 4px;
            background-color: {ModernTheme.APP_BACKGROUND};
            text-align: center;
        }}
        
        QProgressBar::chunk {{
            background-color: {ModernTheme.ACCENT_PURPLE};
            border-radius: 3px;
        }}
        
        /* Tab Widget Styling */
        QTabWidget::pane {{
            border: 1px solid {ModernTheme.BORDER_COLOR};
            background-color: {ModernTheme.APP_BACKGROUND};
        }}
        
        QTabBar::tab {{
            background-color: {ModernTheme.WIDGET_BACKGROUND};
            color: {ModernTheme.TEXT_SECONDARY};
            padding: 10px 20px;
            border-top-left-radius: 5px;
            border-top-right-radius: 5px;
            margin-right: 2px;
        }}
        
        QTabBar::tab:selected {{
            background-color: {ModernTheme.ACCENT_PURPLE};
            color: {ModernTheme.APP_BACKGROUND};
            font-weight: bold;
        }}
        
        QTabBar::tab:hover {{
            background-color: {ModernTheme.BORDER_COLOR};
        }}
        
        QToolTip {{
            background-color: {ModernTheme.WIDGET_BACKGROUND};
            color: {ModernTheme.TEXT_PRIMARY};
            border: 1px solid {ModernTheme.ACCENT_PURPLE};
            border-radius: 4px;
            padding: 5px;
        }}

        /* Header View Styling (Columns) */
        QHeaderView {{
            background-color: transparent;
            border: none;
        }}

        QHeaderView::section {{
            background-color: {ModernTheme.WIDGET_BACKGROUND};
            color: {ModernTheme.TEXT_PRIMARY};
            padding: 4px;
            border: none;
            border-bottom: 1px solid {ModernTheme.BORDER_COLOR};
            font-weight: bold;
        }}

        QHeaderView::section:hover {{
            background-color: {ModernTheme.BORDER_COLOR};
        }}
        
        QHeaderView::section:checked {{
             background-color: {ModernTheme.ACCENT_BLUE};
             color: white;
        }}
        """