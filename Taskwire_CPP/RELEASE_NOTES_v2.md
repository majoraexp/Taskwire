# Taskwire v2.0.0 — Native C++ Qt6 Rewrite

## Performance

- **~31% lower memory usage** (174 MB vs 253 MB RSS)
- **98% smaller binary** (990 KB native vs 51 MB Nuitka bundle)
- **No Python GIL** — UI thread never blocked by interpreter lock
- **Direct /proc and /sys parsing** — zero psutil overhead, zero subprocess spawning for CPU/memory/disk IO/network/temps/fans
- **Faster startup** — no Python interpreter or module import chain

## New Features

- **Friendly sensor names** — raw kernel driver names (k10temp, amdgpu, acpitz, r8169) mapped to human-readable labels (CPU Package, GPU Edge, ACPI, Network). NVMe sensors show actual device model name (e.g., "Samsung SSD 990 PRO 2TB: Composite")
- **Sensor label deduplication** — duplicate labels automatically suffixed with #1, #2, etc.
- **Persistent sensor visibility** — temperature and fan sensor checkbox states saved and restored on next launch
- **Persistent disk drive selection** — last selected drive remembered across restarts
- **Persistent process column selections** — customized column layouts for both Grouped and Detail views saved and restored
- **Persistent theme selection** — last used theme (dark/light) remembered across restarts
- **Scrollable sensor legends** — temperature legend scrolls vertically to accommodate any number of sensors; fan legend compact single-row at bottom
- **Auto-show fan sensors** — hidden fan sensors automatically re-enable when RPM becomes nonzero
- **Improved light theme** — softer off-white background (#e8e8e8/#f0f0f0) instead of harsh bright white; theme-adaptive accent colors (navy blue in light mode, cyan in dark mode) for headers, graphs, gauges, and CPU per-thread widget

## Architecture Improvements

- **Separated polling tiers** — 500ms fast (CPU, memory, GPU, temps, fans, disk IO, network), 1s medium (processes), 5s slow (disk usage only)
- **Thread-safe worker** — dedicated QThread with QTimer-based polling, proper BlockingQueuedConnection shutdown
- **Async service refresh** — ServicesWidget uses non-blocking QProcess pipeline
- **UTF-8-safe journal streaming** — byte-level buffering with forced-decode fallback for pathological streams
- **Generation-based stale signal protection** — prevents race conditions when restarting QProcess instances
