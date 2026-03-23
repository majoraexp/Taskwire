cmake_minimum_required(VERSION 3.16)
project(Taskwire VERSION 1.0.0 LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_AUTOMOC ON)

find_package(Qt6 REQUIRED COMPONENTS Core Gui Widgets)

add_executable(taskwire
    src/main.cpp
    src/mainwindow.cpp
    src/styles.cpp
    src/circulargauge.cpp
    src/systemmonitor.cpp
    src/base.cpp
    src/gaugewidget.cpp
    src/historywidget.cpp
    src/graphutils.cpp
    src/cpuwidget.cpp
    src/memorywidget.cpp
    src/tempgraphwidget.cpp
    src/diskwidget.cpp
    src/networkwidget.cpp
    src/fangraphwidget.cpp
    src/toppanel.cpp
    src/processlistwidget.cpp
    src/serviceswidget.cpp
    src/connectionswidget.cpp
    src/journalwidget.cpp
    src/toolswidget.cpp
)

target_link_libraries(taskwire PRIVATE
    Qt6::Core
    Qt6::Gui
    Qt6::Widgets
)

# Install rules (used by AppImage build and system packaging)
install(TARGETS taskwire DESTINATION bin)
install(FILES taskwire.desktop DESTINATION share/applications)
install(FILES app_icon.png DESTINATION share/icons/hicolor/512x512/apps RENAME taskwire.png)
