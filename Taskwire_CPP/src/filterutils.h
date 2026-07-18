#pragma once

#include <QString>
#include <QRegularExpression>

namespace FilterUtils {

// Match text against a filter pattern.
// Supports wildcard '*' (glob-style): "fire*" matches "firefox", "*ssh*" matches "openssh-server"
// Without wildcards, falls back to substring contains matching.
// All matching is case-insensitive.
inline bool matchesFilter(const QString &text, const QString &filter)
{
    if (filter.isEmpty())
        return true;

    if (filter.contains(QLatin1Char('*'))) {
        // Convert glob pattern to regex: escape everything, then replace \* with .*
        QString pattern = QRegularExpression::escape(filter);
        pattern.replace(QStringLiteral("\\*"), QStringLiteral(".*"));
        QRegularExpression re(
            QStringLiteral("^") + pattern + QStringLiteral("$"),
            QRegularExpression::CaseInsensitiveOption
        );
        return re.match(text).hasMatch();
    }

    return text.toLower().contains(filter.toLower());
}

} // namespace FilterUtils
