#pragma once

#include <QWidget>

class QLabel;
class QPushButton;
class QVBoxLayout;
class QHBoxLayout;

class ToolsWidget : public QWidget {
    Q_OBJECT

public:
    explicit ToolsWidget(QWidget *parent = nullptr);

    void refreshTheme();

private slots:
    void refreshCapsStatus();
    void toggleCapsLock();

private:
    enum class CapsState { Enabled, Disabled, Unknown, Busy };

    void applyCapsState(CapsState state);

    // UI elements
    QVBoxLayout *m_mainLayout;
    QLabel *m_header;
    QWidget *m_capsCard;
    QLabel *m_capsLabel;
    QLabel *m_capsStatusText;
    QWidget *m_capsLed;
    QPushButton *m_capsBtn;

    CapsState m_capsState = CapsState::Unknown;

    static const char *s_capsControlScript;
};
