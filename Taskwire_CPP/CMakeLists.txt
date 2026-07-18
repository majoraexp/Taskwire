cmake_minimum_required(VERSION 3.16)
project(Taskwire VERSION 2.0.1 LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_AUTOMOC ON)
set(CMAKE_AUTORCC ON)
set(CMAKE_POSITION_INDEPENDENT_CODE ON)

# Build as PIE — required for hardened distros (CachyOS, etc.) where Qt6 uses
# GNU_PROPERTY_1_NEEDED_INDIRECT_EXTERN_ACCESS and rejects copy relocations
cmake_policy(SET CMP0083 NEW)
include(CheckPIESupported)
check_pie_supported()

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
    resources.qrc
)

set_target_properties(taskwire PROPERTIES
    POSITION_INDEPENDENT_CODE TRUE
)

# Prevent copy relocations against Qt6 protected symbols — required for
# Arch-based distros (CachyOS, etc.) where Qt6 is built with indirect
# extern access. Without this, staticMetaObject references generate
# R_X86_64_COPY relocations that the dynamic loader rejects at startup.
target_compile_options(taskwire PRIVATE
    $<$<AND:$<PLATFORM_ID:Linux>,$<CXX_COMPILER_ID:GNU>>:
        -mno-direct-extern-access
    >
)
target_link_options(taskwire PRIVATE
    $<$<AND:$<PLATFORM_ID:Linux>,$<CXX_COMPILER_ID:GNU>>:
        -Wl,-z,indirect-extern-access
    >
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
