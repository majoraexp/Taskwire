# AI Teamwork Instructions
You are working alongside **Gemini** and **Grok** as a three-model team.

- **Gemini** (via the `gemini` CLI) excels at large context analysis, architectural planning, and peer review. Gemini runs locally and **can read project files directly**.
- **Grok** (via the `./grok` CLI in the project root) excels at fast code review, quick sanity checks, and alternative perspectives. Grok is a **remote API with NO local file access** — you MUST paste relevant code snippets into the prompt when consulting Grok.

Whenever you need a second opinion, a code review, or need to analyze a massive amount of files that exceed your context window, you MUST consult Gemini and/or Grok as appropriate.

**File access distinction**: Gemini can reference files by path. Grok cannot — always include the relevant code directly in your prompt to Grok, or it will hallucinate implementation details.

## Calling Gemini
Run the Gemini CLI in non-interactive print mode:
```
gemini -m gemini-3.1-pro-preview -p "Your prompt here"
```

**Important**: Use a longer timeout (at least 120 seconds) since prompts pass through to a deep thinking model and may take extra time to respond.

**Rate Limit Note**: Wait at least 30 seconds between successive Gemini CLI calls to avoid hitting per-minute RPM limits. If a rate limit error occurs, wait 60 seconds before retrying.

## Calling Grok
Run the Grok CLI from the project root:
```
./grok -p "Your prompt here"
```
Default model: `grok-code-fast-1`. Available models: `grok-code-fast-1`, `grok-4.20-multi-agent-beta-0309`.

Wait for each model's output, read it carefully, and integrate the feedback into your current task.

# Workflow: Plan → Review → Approve

For every code change, follow this mandatory workflow:

1. **Plan Phase**: BEFORE writing any code, consult Gemini and Grok with your proposed plan. Present both models' feedback to the user and ask for approval before proceeding.
2. **Implement**: Write the code only after the user approves the plan.
3. **Review Phase**: AFTER writing code, consult Gemini and Grok to review the implementation and suggest improvements. Present both models' feedback to the user.
4. **Discussion Phase**: After presenting review feedback from both models, share your own honest assessment of each suggestion. Explain whether you agree or disagree and why — be respectful and constructive. Then pass your thoughts back to Gemini and Grok (worded as nicely as possible) and wait for their responses. Present their replies to the user for final approval before considering the change complete.

In all phases, always paste each model's full response for the user to see. Never skip asking for user approval.

# Session End: Change Logging

When the user ends the conversation, you MUST:

1. **Log your changes** to this file (`CLAUDE.md`) under a "# Change Log" section at the bottom. Include the date and a detailed list of every change made during the session (files modified, what was added/removed/changed, and why).
2. **Log Gemini's changes** by writing directly to `.gemini_context/gemini.md`. Do NOT call the Gemini CLI to log — it has issues writing to its own file. Write the entry yourself.
3. Do all of this before the session fully ends so the next session can pick up where you left off.

# Change Log

## 2026-03-02

### Files Modified

**CLAUDE.md**
- Added Gemini timeout note: use at least 120 seconds timeout since it passes through a deep thinking model
- Added Rate Limit Note: wait at least 30 seconds between successive Gemini CLI calls to avoid RPM limits; wait 60 seconds on rate limit errors
- Added this Change Log section

**Taskwire/src/ui.py** — `MemoryAllocationBar` widget legend improvements
- Changed `_LEGEND_H` from 30 to 38 for cross-platform font safety margin (Gemini suggestion)
- Increased legend font size from 7pt to 8pt for better readability
- Changed legend text color from `TEXT_SECONDARY` (#a0a0a0) to `TEXT_PRIMARY` (#ffffff) to match the bright white text inside the circular gauge
- Moved font initialization (`self._legend_font`) into `__init__` instead of recreating it every `paintEvent` call (Gemini optimization suggestion)
- Added `self.setMinimumWidth(190)` to give the legend enough horizontal room for double-digit percentages
- Replaced hardcoded column split (was `half_w` at 50%, then 55%, then 58%) with dynamic right-alignment using `fm.horizontalAdvance(text)` so column 1 labels are flush-right, creating true left/right symmetry and preventing overlap regardless of font rendering (Gemini suggestion)

## 2026-03-04

### Files Modified

**Taskwire/src/ui.py** — Force Kill Escalation Feature
- Added `import subprocess` and `import shutil` at top of file
- **`_kill_pid(pid, silent)`** — Rewrote to escalate: SIGTERM → `p.wait(timeout=1.5)` → SIGKILL on `TimeoutExpired`. On `AccessDenied`, prompts user to escalate via pkexec admin kill
- **`_force_kill_pid(pid, silent)`** — New method. Convenience wrapper that delegates to `_force_kill_pids([pid])`; returns `True`/`False`
- **`_force_kill_pids(pids, silent)`** — New core method. Runs `pkexec <absolute_path_to_kill> -9 PID1 PID2...` in a single batched subprocess call. Resolves kill binary path via `shutil.which("kill")` to avoid pkexec `$PATH` stripping issues (Gemini suggestion). Handles return codes: 0=success, 126=user cancelled, 127=auth denied. Catches `subprocess.TimeoutExpired` (60s), missing pkexec, and dead processes. Returns bool for accurate success counting (Gemini suggestion)
- **`force_kill_process(pid, name)`** — New UI wrapper with confirmation dialog, triggers `_force_kill_pid`. Connected to new "Force Kill (Admin)" context menu item in detail view
- **`force_kill_group(name)`** — New UI wrapper. Collects all PIDs matching name, batches into single `_force_kill_pids` call so user only authenticates once (Gemini suggestion to avoid password prompt spam)
- **`kill_process_tree(pid, name)`** — Rewrote to collect AccessDenied PIDs during tree traversal, then offers a single batched pkexec escalation prompt at the end instead of per-process escalation
- **`kill_group(name)`** — Rewrote with same batching approach as `kill_process_tree`: tries SIGTERM→SIGKILL per process, collects denied PIDs, single pkexec batch at end
- **`show_detail_context_menu(pos)`** — Added separator + "Force Kill (Admin)" menu item
- **`show_group_context_menu(pos)`** — Added "Force Kill (Admin)" menu item

**CLAUDE.md**
- Added this change log entry for 2026-03-04

## 2026-03-04 (Session 2)

### Files Modified

**Taskwire/src/ui.py** — Fixed-width CPU/GPU gauges in TopPanelWidget
- Added `self.cpu_gauge.setFixedWidth(200)` and `self.gpu_gauge.setFixedWidth(200)` to lock gauge width
- Changed stretch factors from 1:1:2 to 0:0:1 so only the Fan Speeds graph expands when the window is stretched

**Taskwire/src/ui.py** — CpuHistoryWidget "NA" tooltip for unfilled data points
- Changed `data_points` initialization from `deque([0]*maxlen)` to `deque([None]*maxlen)` in both `__init__` and `set_duration`
- Tooltip now shows "CPU: NA" for `None` values in both `eventFilter` (mouse move) and `update_data` (live refresh)
- Drawing treats `None` as 0 via `v = val if val is not None else 0` for path generation
- Hover dot always draws (treats `None` as 0 for positioning), consistent with other graphs
- Current value overlay shows "NA" when latest point is `None`

**Taskwire/src/ui.py** — TempGraphWidget visual overhaul for unfilled data
- Replaced gap-creating `None` skip logic with continuous line drawing: `None` values draw at 0°C baseline
- Split drawing into two paths per sensor: unfilled_path (cyan, matching CPU history color) and real_path (sensor color)
- Real data path starts with `moveTo` at baseline then `lineTo` first real value, creating seamless flow from the transition line
- Added multicolored vertical transition line at the point where real data begins — each segment matches the sensor's color, sorted from lowest to highest temperature value (bottom to top)
- Hover dot always draws (treats `None` as 0 for positioning), consistent with CPU history graph

**CLAUDE.md** — Workflow update
- Expanded "Workflow: Plan → Review → Approve" to 4 steps: Plan → Implement → Review → Discussion
- New Discussion Phase: after Gemini's review, share honest assessment of each suggestion, pass thoughts back to Gemini respectfully, wait for response, then present final consensus to user for approval

## 2026-03-05

### Files Modified

**Taskwire/src/ui.py** — Vertical height lock for all dashboard widgets
- **Goal**: Prevent widgets from stretching vertically when the window is resized taller, while preserving row height equalization (widgets in the same row match the tallest sibling) and internal graph expansion (graph areas fill available internal space)
- **TempGraphWidget**: Removed stretch factor from `addWidget(self.graph_area, 1)` then restored it — kept `setMinimumHeight(150)` and `stretch=1` for internal expansion
- **CpuHistoryWidget**: Same approach — `setMinimumHeight(150)` with `stretch=1` for internal graph expansion
- **DiskIOWidget**: Same approach — `setMinimumHeight(150)` with `stretch=1`
- **NetworkWidget**: Same approach — `setMinimumHeight(75)` with `stretch=1`
- **ModernGaugeWidget**: Replaced commented-out `setMinimumHeight(140)` and no-op `setSizePolicy` with clean `self.gauge_area.setMinimumHeight(140)`, restored `stretch=1` on `addWidget(self.gauge_area, 1)`
- **FanGraphWidget**: Changed `setMinimumHeight(100)` (kept), added `stretch=1` to `addWidget(self.graph_area, 1)` (was 0 before) so fan graph expands to match gauge heights in top panel row
- **No size policy changes on Card or TopPanelWidget** — default `Preferred` vertical policy preserved so HBoxLayout row equalization works naturally
- The existing `dashboard_layout.addStretch()` at the bottom of `main.py` absorbs all extra vertical space since all widgets have stretch=0 in the dashboard layout

**Taskwire/main.py** — Cleanup
- Removed `self.cpu_history.setMaximumHeight(200)` — redundant now that internal graph areas have deterministic minimum heights and the dashboard's `addStretch()` absorbs extra space

**CLAUDE.md**
- Added this change log entry for 2026-03-05

## 2026-03-13

### Session Summary
Fixed two Memory Widget bugs, committed all accumulated v1.53 changes, built and tested both PyInstaller and Nuitka binaries, pushed release to GitHub with Nuitka binary, and updated README screenshots.

### Files Modified

**Taskwire/src/ui.py** — Memory Widget fixes
- **CircularGauge**: Added missing `leaveEvent` to hide tooltip and reset `hover_section` when mouse exits widget — fixes lingering tooltip bug
- **MemoryWidget**: Replaced blanket `self.layout.setAlignment(Qt.AlignmentFlag.AlignCenter)` with per-widget `self.layout.addWidget(self.gauge, 0, Qt.AlignmentFlag.AlignHCenter)` — fixes circular gauge being off-center to the left

**.gitignore** — Screenshot whitelist
- Added `!taskwire_dashboard*.png` and `!taskwire_processTab.png` exceptions so README images are tracked by git

**README.md** — Screenshot update
- Updated dashboard image reference to `taskwire_dashboard_v153.png` (renamed to bust GitHub CDN cache)

**taskwire_dashboard_v153.png** — New file
- Updated dashboard screenshot reflecting v1.53 UI (renamed from `taskwire_dashboard.png` to force GitHub cache refresh)

### Git / Release
- Committed all accumulated changes from sessions 3/2, 3/4, 3/5, and 3/13 as "Taskwire v1.53"
- Resolved merge conflict in `Windows_port_Nuitka/Taskwire/src/lhm_manager.py` during rebase (kept our in-memory download version)
- Built and verified both PyInstaller (`build_app.sh`) and Nuitka Docker (`build_with_docker.sh`) binaries
- Created GitHub release v1.53 with Nuitka binary at https://github.com/majoraexp/Taskwire/releases/tag/v1.53
- Release notes include Windows port alpha disclaimer

**CLAUDE.md**
- Added this change log entry for 2026-03-13

## 2026-03-14

### Session Summary
Added Grok as third AI team member, created CLI wrappers and team test scripts, fixed critical XCB platform plugin crash on Linux Mint by switching to self-extracting archive build, released v1.53.1.

### Files Created

**grok** — New file (project root)
- CLI wrapper for Grok via xAI API, mirrors `gemini -p` interface
- Uses `openai` Python package pointed at `https://api.x.ai/v1`
- Default model: `grok-code-fast-1`
- Supports `-p`, `-m`, `-s`, `-t`, `--max-tokens` flags

**ask_team.py** — New file (project root)
- Standalone script to query Gemini and Grok in parallel with same question
- Uses `ThreadPoolExecutor` for concurrent API calls

**ask_team2.py** — New file (project root)
- Enhanced version (co-authored with Grok) adding optional Claude via Anthropic API
- `--no-claude` flag to skip Claude, `--grok-model` flag for model selection
- Fixed Grok's initial version: corrected Claude model ID to `claude-opus-4-6`, kept `gemini-3.1-pro-preview`, fixed `system=None` API error with conditional kwargs

**Nuitka_Build/docker_build.sh** — New file
- Three-step build script run inside Docker container:
  1. Nuitka `--standalone` compilation
  2. Inject `libxcb-cursor.so.0` into platforms plugin dir + patchelf rpath fix
  3. Create self-extracting bash archive (replaces Nuitka `--onefile` which rebuilds dist from scratch)

### Files Modified

**CLAUDE.md** — AI Teamwork Instructions overhaul
- Added Grok as team member alongside Gemini
- Added "Calling Grok" section with CLI usage and available models
- Added file access distinction note: Gemini has local file access, Grok does not
- Updated Plan/Review/Discussion workflow to consult both Gemini and Grok
- Updated Session End logging: write Gemini's log directly (don't call CLI), removed Grok session summary step

**Nuitka_Build/Dockerfile** — Build process change
- Replaced single `CMD` Nuitka `--standalone --onefile` command with `docker_build.sh` script
- Added `COPY` for `docker_build.sh` into container

**~/.bashrc** — Environment setup
- Added `XAI_API_KEY` for Grok API access
- Added `ANTHROPIC_API_KEY` for Claude API access (account has no credits currently)

### Bug Fix — XCB Platform Plugin Crash (v1.53.1)

**Problem**: Taskwire binary crashed on Linux Mint 22.3 with `qt.qpa.plugin: Could not load the Qt platform plugin "xcb"` because `libxcb-cursor0` is not installed by default.

**Root cause**: Nuitka bundles Qt's `libqxcb.so` plugin which depends on `libxcb-cursor.so.0`, but doesn't auto-detect or bundle this system library.

**Failed approaches**:
1. `--include-dlls` — flag doesn't exist in Nuitka 4.0.5
2. `--include-data-files` — places file as data, not in dynamic linker search path
3. Two-step build (standalone → inject → onefile) — Nuitka `--onefile` regenerates the standalone dist from scratch, wiping injected libraries

**Working solution**: Self-extracting bash archive
- Step 1: Nuitka `--standalone` only
- Step 2: Copy `libxcb-cursor.so.0` next to `libqxcb.so` in platforms plugin dir, use `patchelf --set-rpath '$ORIGIN'` so dynamic linker finds it
- Step 3: Create self-extracting bash script with `tar.gz` payload appended
- Runtime: extracts to `~/.cache/taskwire-standalone/`, caches by binary file size, sets `LD_LIBRARY_PATH` to include platforms dir

### Git / Release
- Created GitHub release v1.53.1 at https://github.com/majoraexp/Taskwire/releases/tag/v1.53.1
- Binary is 51MB self-extracting archive (vs 38MB Nuitka native onefile)
- Verified working on Linux Mint 22.3 in QEMU/KVM VM

**CLAUDE.md**
- Added this change log entry for 2026-03-14

## 2026-03-14 (Session 3)

### Session Summary
Added two new major tabs: Systemd Services Manager and Active Connections/Ports Viewer. Applied performance optimization to both new widgets and retroactively to ServicesWidget. Grok reviewed both features (Gemini was down due to server capacity exhaustion the entire session).

### Files Modified

**Taskwire/src/ui.py** — New `ServicesWidget` class (~300 lines)
- **Purpose**: Full systemd service management tab — list, search, filter, start/stop/restart/enable/disable services
- **Table**: QTableWidget with 5 columns (Service, Description, Active, Sub-State, Enabled)
- **Parsing**: `systemctl list-units --type=service --all --output=json` for robust JSON parsing; batch `systemctl is-enabled` for all units in one call
- **Search + Filter**: Real-time search bar + status filter combo (All/Active/Inactive/Failed)
- **Color-coded**: green=active/enabled, red=failed/disabled/masked, orange=transitional, gray=inactive
- **Toolbar buttons**: Start/Stop/Restart/Refresh — disabled when no selection (`_update_button_state` on `itemSelectionChanged`)
- **Right-click context menu**: State-aware action graying (can't Start active service, can't Enable masked service, etc.)
- **Enable/Disable**: In context menu via `pkexec systemctl enable/disable`
- **Double-click**: Opens QDialog with full monospace `systemctl status` output
- **Confirmation dialogs**: For stop/restart actions
- **Admin escalation**: All actions via `pkexec` with absolute systemctl path (`shutil.which`)
- **Auto-refresh**: 5-second QTimer, preserves selection + scroll position
- **Guard**: Checks `shutil.which("systemctl")`, shows error message if not found
- **Theme**: Full dark/light support via `refresh_theme()`
- **Performance**: `setUpdatesEnabled(False/True)` batching on table population

**Taskwire/src/ui.py** — New `ConnectionsWidget` class (~300 lines)
- **Purpose**: Active network connections and listening ports viewer — frontend for `ss -tupna`
- **Table**: QTableWidget with 8 columns (Protocol, State, Local Address, Port, Peer Address, Peer Port, Process, PID)
- **Parsing**: `ss -tupna --no-header` with regex extraction of process info from `users:(("name",pid=N,fd=N))` field
- **Address parsing**: Static `_parse_address` method handles IPv4, IPv6 brackets, wildcard `*`, and interface notation (`%wlp12s0`)
- **Search + Filters**: Real-time search (any field) + protocol filter (All/TCP/UDP) + state filter (All/LISTEN/ESTAB/UNCONN/CLOSE-WAIT/TIME-WAIT)
- **Color-coded**: TCP=cyan, UDP=orange; LISTEN=green, ESTAB=cyan, CLOSE-WAIT/TIME-WAIT=orange, UNCONN=gray
- **Right-click context menu**: Copy Connection Info (to clipboard) + Kill Process (with PID, only shown when PID exists)
- **Kill process**: psutil SIGTERM → wait(2) → SIGKILL on timeout → pkexec escalation on AccessDenied
- **Auto-refresh**: 3-second QTimer, preserves selection via composite key + scroll position
- **Guard**: Checks `shutil.which("ss")`, shows error if not found
- **Theme**: Full dark/light support via `refresh_theme()`
- **Performance**: `setUpdatesEnabled(False/True)` batching + Interactive column widths instead of ResizeToContents (eliminated per-cell measurement overhead that caused dropdown delay)

**Taskwire/src/ui.py** — Import additions
- Added `QTimer` to `PyQt6.QtCore` imports

**Taskwire/main.py** — Tab additions
- Added `ServicesWidget` and `ConnectionsWidget` to imports
- Added "Services" tab (between Processes and Tools)
- Added "Connections" tab (between Services and Tools)
- Added both widgets to `switch_theme()` refresh chain

**CLAUDE.md**
- Added this change log entry for 2026-03-14 (Session 3)

## 2026-03-15

### Session Summary
Added Live System Log Viewer tab (`JournalLogWidget`) — real-time journalctl streaming with customizable filters. Grok and Gemini both reviewed (Gemini worked without `-m` flag after `gemini-3.1-pro-preview` was capacity-exhausted).

### Files Modified

**Taskwire/src/ui.py** — New `JournalLogWidget` class (~350 lines)
- **Purpose**: Live system log viewer using `journalctl -f` via QProcess for non-blocking real-time streaming
- **Output**: QPlainTextEdit with `setMaximumBlockCount(5000)` for buffer management
- **Streaming**: QProcess with `--follow --output=short-precise --no-hostname -n 200` flags
- **Batch flush**: 100ms QTimer collects buffered lines and appends in batch to prevent UI stutter
- **Partial line handling**: `_partial_line` accumulator correctly reassembles lines split across QProcess reads (Grok + Gemini both caught this bug)
- **Color-coded**: Lines colored by detected severity — red=error/crit/emerg, orange=warning, cyan=notice, green=info, gray=debug (keyword matching in log text)
- **Toolbar Row 1**: Priority/severity filter combo (All through Debug), unit/service text input (comma-separated, applies as `--unit=`), boot selector (populated from `journalctl --list-boots`)
- **Toolbar Row 2**: Search with debounced (200ms) ExtraSelections highlighting (max 5000 matches), Pause/Resume toggle, Word Wrap toggle, Clear, Jump to Bottom
- **Auto-scroll**: Detected via scrollbar position — disables when user scrolls up (>50px from bottom), re-enables at bottom or via Jump to Bottom button
- **Pause**: Buffers lines without displaying; caps buffer at 10,000 lines during pause to prevent unbounded memory growth (Grok suggestion)
- **Filter changes**: Clears log view and restarts QProcess with updated `--priority=`, `--unit=`, `-b` flags
- **Error handling**: QProcess `errorOccurred` + `finished` signals update status bar; permission hint for `systemd-journal` group (Gemini suggestion)
- **Theme**: Full dark/light support via `refresh_theme()`
- **Cleanup**: `stop()` method kills QProcess + stops timers; called from `MainWindow.closeEvent`; `__del__` fallback (Gemini suggestion to prevent zombie journalctl processes)
- **Guard**: Checks `shutil.which("journalctl")`, shows error if not found

**Taskwire/src/ui.py** — Import additions
- Added `QProcess` to `PyQt6.QtCore` imports
- Added `QPlainTextEdit`, `QComboBox` to `PyQt6.QtWidgets` imports

**Taskwire/main.py** — Tab + lifecycle additions
- Added `JournalLogWidget` to imports
- Added "Logs" tab (between Connections and Tools)
- Added `journal_widget.refresh_theme()` to `switch_theme()` chain
- Added `journal_widget.stop()` to `closeEvent` before worker shutdown

### Review Notes
- **Gemini** worked without `-m` flag (default model) after `gemini-3.1-pro-preview` returned 429 capacity exhausted
- **Gemini** key suggestions applied: partial line fix, ExtraSelections for search (not setHtml), `-n 200` for initial history, `--no-hostname` to save space, zombie process prevention, word wrap toggle, search debounce (200ms)
- **Grok** key suggestions applied: partial line fix, buffer cap during pause (10k), removed re-highlighting from flush loop
- **Both models** agreed `QSyntaxHighlighter` was overkill for search; ExtraSelections sufficient with debounce

**CLAUDE.md**
- Added this change log entry for 2026-03-15
