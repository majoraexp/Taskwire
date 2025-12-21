"""
This module defines the ModernTheme class for consistent styling across the application.
It provides color palettes and a stylesheet generator for PyQt6 widgets.
"""

class ModernTheme: # pylint: disable=R0903
    """
    Defines the color palette and provides a static method to generate
    the application's QSS (Qt Style Sheet) for a consistent look and feel.
    """
    # Color Palette
    APP_BACKGROUND = "#121212"  # Very dark, almost black
    WIDGET_BACKGROUND = "#1e1e2e" # Slightly lighter, blueish-black
    TEXT_PRIMARY = "#ffffff"
    TEXT_SECONDARY = "#a0a0a0"
    
    # Accents (Neon-like)
    ACCENT_RED = "#ff5555"
    ACCENT_GREEN = "#50fa7b"
    ACCENT_BLUE = "#6272a4" # Dracula theme style blue
    ACCENT_CYAN = "#8be9fd"
    ACCENT_PURPLE = "#bd93f9"
    ACCENT_ORANGE = "#ffb86c"
    ACCENT_YELLOW = "#f1fa8c"

    # Borders
    BORDER_COLOR = "#44475a"

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
            background-color: rgba(30, 30, 46, 150);
            color: #ffffff;
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
