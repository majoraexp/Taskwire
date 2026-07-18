#include <QApplication>
#include <QSettings>
#include <QIcon>
#include "mainwindow.h"
#include "styles.h"
#include "systemmonitor.h"

int main(int argc, char *argv[]) {
    QApplication app(argc, argv);
    app.setOrganizationName("Taskwire");
    app.setApplicationName("Taskwire");

    // Icon is embedded via resources.qrc — works regardless of install location
    app.setWindowIcon(QIcon(QStringLiteral(":/app_icon.png")));

    // Register metatypes for cross-thread signal/slot
    qRegisterMetaType<CpuStats>("CpuStats");
    qRegisterMetaType<MemoryStats>("MemoryStats");
    qRegisterMetaType<GpuStats>("GpuStats");
    qRegisterMetaType<DiskUsageStats>("DiskUsageStats");
    qRegisterMetaType<DiskIoStats>("DiskIoStats");
    qRegisterMetaType<NetworkStats>("NetworkStats");
    qRegisterMetaType<TempStats>("TempStats");
    qRegisterMetaType<FanStats>("FanStats");
    qRegisterMetaType<ProcessStats>("ProcessStats");

    // Initialize theme (restore last used, default to dark)
    QSettings settings;
    QString theme = settings.value(QStringLiteral("theme"), QStringLiteral("dark")).toString();
    ModernTheme::setTheme(theme);
    app.setStyleSheet(ModernTheme::getStylesheet());

    MainWindow window;
    window.show();

    return app.exec();
}
