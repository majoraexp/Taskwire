#pragma once
#include <QString>
#include <QColor>

struct Palette {
    QString appBackground;
    QString widgetBackground;
    QString textPrimary;
    QString textSecondary;

    QString accentRed;
    QString accentGreen;
    QString accentBlue;
    QString accentCyan;
    QString accentPurple;
    QString accentOrange;
    QString accentYellow;

    QString borderColor;
    QString alternateTableBg;
};

class ModernTheme {
public:
    static void setTheme(const QString &mode);
    static QString getStylesheet();

    static inline QString appBackground;
    static inline QString widgetBackground;
    static inline QString textPrimary;
    static inline QString textSecondary;

    static inline QString accentRed;
    static inline QString accentGreen;
    static inline QString accentBlue;
    static inline QString accentCyan;
    static inline QString accentPurple;
    static inline QString accentOrange;
    static inline QString accentYellow;

    static inline QString borderColor;
    static inline QString alternateTableBg;

private:
    static const Palette darkPalette;
    static const Palette lightPalette;
};
