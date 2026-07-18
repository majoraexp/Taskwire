#include "styles.h"
#include <QApplication>
#include <QPalette>

const Palette ModernTheme::darkPalette = {
    "#121212", "#1e1e2e", "#ffffff", "#a0a0a0",
    "#ff5555", "#50fa7b", "#6272a4", "#8be9fd",
    "#bd93f9", "#ffb86c", "#f1fa8c",
    "#44475a", "#2a2a3a"
};

const Palette ModernTheme::lightPalette = {
    "#e8e8e8", "#f0f0f0", "#2f3640", "#718093",
    "#e84118", "#44bd32", "#273c75", "#0097e6",
    "#8c7ae6", "#e1b12c", "#fbc531",
    "#d0d0d0", "#e4e4e4"
};

void ModernTheme::setTheme(const QString &mode) {
    const Palette &p = (mode == "light") ? lightPalette : darkPalette;

    appBackground   = p.appBackground;
    widgetBackground = p.widgetBackground;
    textPrimary     = p.textPrimary;
    textSecondary   = p.textSecondary;

    accentRed    = p.accentRed;
    accentGreen  = p.accentGreen;
    accentBlue   = p.accentBlue;
    accentCyan   = p.accentCyan;
    accentPurple = p.accentPurple;
    accentOrange = p.accentOrange;
    accentYellow = p.accentYellow;

    borderColor     = p.borderColor;
    alternateTableBg = p.alternateTableBg;

    // Set QPalette highlight to match stylesheet selection color
    QPalette pal = qApp->palette();
    pal.setColor(QPalette::Highlight, QColor(p.accentBlue));
    pal.setColor(QPalette::HighlightedText, Qt::white);
    qApp->setPalette(pal);
}

QString ModernTheme::getStylesheet() {
    // Arg mapping:
    //   %1 = appBackground       %2 = textPrimary        %3 = borderColor
    //   %4 = widgetBackground    %5 = textSecondary      %6 = accentPurple
    //   %7 = alternateTableBg    %8 = accentBlue
    return QString(R"(

/* ── Global rules (safe for all widgets including dashboard) ─── */

QMainWindow { background-color: %1; }

QWidget {
    background-color: %1;
    color: %2;
    font-family: 'Segoe UI', 'Roboto', 'Ubuntu', sans-serif;
    font-size: 14px;
}

QLabel { background-color: transparent; border: none; }

QTabWidget::pane { border: 1px solid %3; background-color: %1; }

QTabBar::tab {
    background-color: %4; color: %5;
    padding: 10px 20px;
    border-top-left-radius: 5px; border-top-right-radius: 5px;
    margin-right: 2px;
}
QTabBar::tab:selected { background-color: %6; color: %1; font-weight: bold; outline: none; border: none; }
QTabBar::tab:selected:focus { outline: none; border: none; }
QTabBar::tab:hover { background-color: %3; }
QTabBar:focus { outline: none; border: none; }

QToolTip {
    background-color: %4; color: %2;
    border: 1px solid %6; border-radius: 4px; padding: 5px;
}

QFrame[class="card"] {
    background-color: %4; border: 1px solid %3; border-radius: 10px;
}

QScrollArea { background: transparent; border: none; }

QTableWidget, QTableView {
    selection-background-color: %8; selection-color: white; outline: none;
}
QTableWidget::item, QTableView::item {
    background-color: transparent;
}
QTableWidget::item:selected, QTableWidget::item:selected:active, QTableWidget::item:selected:!active,
QTableView::item:selected, QTableView::item:selected:active, QTableView::item:selected:!active {
    background-color: %8; color: white;
}

/* ── Menu chrome ─────────────────────────────────────────────── */

QMenuBar {
    background-color: %4; color: %2;
    border-bottom: 1px solid %3;
}
QMenuBar::item {
    background: transparent; padding: 6px 10px; border-radius: 4px;
}
QMenuBar::item:selected { background-color: %6; color: %1; }
QMenuBar::item:pressed  { background-color: %6; color: %1; }

QMenu {
    background-color: %4; color: %2;
    border: 1px solid %3; padding: 4px 0px;
}
QMenu::item { background: transparent; padding: 6px 24px 6px 12px; }
QMenu::item:selected { background-color: %6; color: %1; }
QMenu::item:disabled { color: %5; }
QMenu::separator { height: 1px; background-color: %3; margin: 4px 8px; }

/* ── Scrollbars ──────────────────────────────────────────────── */

QScrollBar:vertical {
    background: transparent; width: 10px;
    margin: 2px 0px; border: none;
}
QScrollBar::handle:vertical {
    background-color: %3; border-radius: 5px; min-height: 24px;
}
QScrollBar::handle:vertical:hover { background-color: %6; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    background: transparent; border: none; height: 0px;
}
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
    background: transparent;
}

QScrollBar:horizontal {
    background: transparent; height: 10px;
    margin: 0px 2px; border: none;
}
QScrollBar::handle:horizontal {
    background-color: %3; border-radius: 5px; min-width: 24px;
}
QScrollBar::handle:horizontal:hover { background-color: %6; }
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
    background: transparent; border: none; width: 0px;
}
QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {
    background: transparent;
}

/* ── Scoped rules: non-dashboard tab widgets only ────────────── */

/* Buttons */
ProcessListWidget QPushButton,
ServicesWidget QPushButton,
ConnectionsWidget QPushButton,
JournalLogWidget QPushButton,
ToolsWidget QPushButton {
    background-color: %4; color: %2;
    border: 1px solid %3; border-radius: 6px;
    font-weight: bold; padding: 4px 10px;
}

ProcessListWidget QPushButton:hover,
ServicesWidget QPushButton:hover,
ConnectionsWidget QPushButton:hover,
JournalLogWidget QPushButton:hover,
ToolsWidget QPushButton:hover {
    border-color: %6; background-color: %4;
}

ProcessListWidget QPushButton:pressed,
ServicesWidget QPushButton:pressed,
ConnectionsWidget QPushButton:pressed,
JournalLogWidget QPushButton:pressed,
ToolsWidget QPushButton:pressed {
    background-color: %6; color: %1; border-color: %6;
}

ProcessListWidget QPushButton:checked,
ServicesWidget QPushButton:checked,
ConnectionsWidget QPushButton:checked,
JournalLogWidget QPushButton:checked,
ToolsWidget QPushButton:checked {
    background-color: %6; color: %1; border-color: %6;
}

ProcessListWidget QPushButton:disabled,
ServicesWidget QPushButton:disabled,
ConnectionsWidget QPushButton:disabled,
JournalLogWidget QPushButton:disabled,
ToolsWidget QPushButton:disabled {
    background-color: %4; color: %5; border-color: %3;
}

/* Line edits */
ProcessListWidget QLineEdit,
ServicesWidget QLineEdit,
ConnectionsWidget QLineEdit,
JournalLogWidget QLineEdit,
ToolsWidget QLineEdit {
    background-color: %1; color: %2;
    border: 1px solid %3; border-radius: 6px;
    padding: 4px 8px;
    selection-background-color: %6; selection-color: %1;
}

ProcessListWidget QLineEdit:hover,
ServicesWidget QLineEdit:hover,
ConnectionsWidget QLineEdit:hover,
JournalLogWidget QLineEdit:hover,
ToolsWidget QLineEdit:hover { border-color: %6; }

ProcessListWidget QLineEdit:focus,
ServicesWidget QLineEdit:focus,
ConnectionsWidget QLineEdit:focus,
JournalLogWidget QLineEdit:focus,
ToolsWidget QLineEdit:focus { border-color: %6; }

ProcessListWidget QLineEdit:disabled,
ServicesWidget QLineEdit:disabled,
ConnectionsWidget QLineEdit:disabled,
JournalLogWidget QLineEdit:disabled,
ToolsWidget QLineEdit:disabled {
    background-color: %1; color: %5; border-color: %3;
}

/* Combo boxes */
ProcessListWidget QComboBox,
ServicesWidget QComboBox,
ConnectionsWidget QComboBox,
JournalLogWidget QComboBox,
ToolsWidget QComboBox {
    background-color: %4; color: %2;
    border: 1px solid %3; border-radius: 6px;
    padding: 4px 28px 4px 8px;
}

ProcessListWidget QComboBox:hover,
ServicesWidget QComboBox:hover,
ConnectionsWidget QComboBox:hover,
JournalLogWidget QComboBox:hover,
ToolsWidget QComboBox:hover { border-color: %6; }

ProcessListWidget QComboBox:focus,
ServicesWidget QComboBox:focus,
ConnectionsWidget QComboBox:focus,
JournalLogWidget QComboBox:focus,
ToolsWidget QComboBox:focus { border-color: %6; }

ProcessListWidget QComboBox:disabled,
ServicesWidget QComboBox:disabled,
ConnectionsWidget QComboBox:disabled,
JournalLogWidget QComboBox:disabled,
ToolsWidget QComboBox:disabled {
    background-color: %1; color: %5; border-color: %3;
}

ProcessListWidget QComboBox QAbstractItemView,
ServicesWidget QComboBox QAbstractItemView,
ConnectionsWidget QComboBox QAbstractItemView,
JournalLogWidget QComboBox QAbstractItemView,
ToolsWidget QComboBox QAbstractItemView {
    background-color: %4; color: %2;
    border: 1px solid %3;
    selection-background-color: %6; selection-color: %1;
}

/* Checkboxes — intentionally do NOT style ::indicator */
ProcessListWidget QCheckBox,
ServicesWidget QCheckBox,
ConnectionsWidget QCheckBox,
JournalLogWidget QCheckBox,
ToolsWidget QCheckBox {
    background: transparent; color: %2; spacing: 6px;
}

ProcessListWidget QCheckBox:disabled,
ServicesWidget QCheckBox:disabled,
ConnectionsWidget QCheckBox:disabled,
JournalLogWidget QCheckBox:disabled,
ToolsWidget QCheckBox:disabled { color: %5; }

/* Tables */
ProcessListWidget QTableWidget,
ProcessListWidget QTableView,
ServicesWidget QTableWidget,
ServicesWidget QTableView,
ConnectionsWidget QTableWidget,
ConnectionsWidget QTableView {
    background-color: %4; alternate-background-color: %7;
    color: %2; gridline-color: %3;
    border: 1px solid %3;
    selection-background-color: %8; selection-color: white;
}

ProcessListWidget QTableWidget::item,
ProcessListWidget QTableView::item,
ServicesWidget QTableWidget::item,
ServicesWidget QTableView::item,
ConnectionsWidget QTableWidget::item,
ConnectionsWidget QTableView::item {
    padding: 3px 6px; border: none;
}

ProcessListWidget QTableWidget::item:selected,
ProcessListWidget QTableView::item:selected,
ServicesWidget QTableWidget::item:selected,
ServicesWidget QTableView::item:selected,
ConnectionsWidget QTableWidget::item:selected,
ConnectionsWidget QTableView::item:selected {
    background-color: %8; color: white;
}

/* Headers */
ProcessListWidget QHeaderView,
ServicesWidget QHeaderView,
ConnectionsWidget QHeaderView {
    background: transparent; border: none;
}

ProcessListWidget QHeaderView::section,
ServicesWidget QHeaderView::section,
ConnectionsWidget QHeaderView::section {
    background-color: transparent; color: %5;
    padding: 6px 8px; border: none;
    border-bottom: 1px solid %3;
}

ProcessListWidget QHeaderView::section:hover,
ServicesWidget QHeaderView::section:hover,
ConnectionsWidget QHeaderView::section:hover {
    background-color: %4; color: %2;
}

ProcessListWidget QHeaderView::section:pressed,
ServicesWidget QHeaderView::section:pressed,
ConnectionsWidget QHeaderView::section:pressed {
    background-color: %6; color: %1;
}

/* Table corner button */
ProcessListWidget QTableCornerButton::section,
ServicesWidget QTableCornerButton::section,
ConnectionsWidget QTableCornerButton::section {
    background-color: transparent; border: none;
    border-right: 1px solid %3; border-bottom: 1px solid %3;
}

)").arg(appBackground, textPrimary, borderColor,
        widgetBackground, textSecondary, accentPurple,
        alternateTableBg, accentBlue);
}
