# ToolsWidget v2 Improvement Plan

Collected from 4-model review (Claude, Gemini, Grok, GPT 5.4) during v1 implementation on 2026-03-22.
All items were explicitly deferred from v1 with reviewer consensus.

## Phase 1: Fix GNOME Architecture

**Problem:** `gsettings` is a user-session operation but currently runs inside the privileged `pkexec` helper via `su - user`. This is inherently fragile — `su -` resets environment, D-Bus session address may be lost, and the enable path doesn't reconstruct the env first.

**Solution:**
- Remove GNOME `gsettings` calls from the embedded Bash helper script
- Run `gsettings set/reset` directly from the C++ app process (runs as the actual user, with correct D-Bus session)
- Preserve existing `xkb-options` array — read current, add/remove only `caps:none`, write back (same improvement already made for `localectl`)
- Helper functions needed: `parseGsettingsArray(QString) -> QStringList`, `formatGsettingsArray(QStringList) -> QString`

**Same applies to KDE:** User config file edits (`kxkbrc`) don't need root. Move them out of the privileged helper too. Only `localectl` and `loadkeys` actually need elevation.

**Concrete split:**
- Privileged helper (pkexec): `localectl set-x11-keymap`, `loadkeys`/`dumpkeys`
- Normal app process: GNOME `gsettings`, KDE `kxkbrc` edits, `setxkbmap`

## Phase 2: Async Toggle Execution

**Problem:** `toggleCapsLock()` blocks the UI thread with `waitForStarted(5000)` + `waitForFinished(60000)`. The polkit auth dialog is modal so the user can't interact with the app anyway, but dashboard graphs stall and the app appears hung.

**Solution:**
- Create a `CapsToggleOperation : QObject` class that manages the async flow
- Use `QProcess` signals (`finished`, `errorOccurred`, `readyReadStandardOutput/Error`) instead of blocking waits
- Add timeout via `QTimer::singleShot(30000, ...)` instead of `waitForFinished(60000)`
- `QTemporaryFile` must become a member (`std::unique_ptr<QTemporaryFile>`) for async lifetime management
- Clean up in `finished()`/`errorOccurred()` signal handlers

**UI improvements enabled by async:**
- Progressive status updates: "Waiting for authentication..." -> "Applying system setting..." -> "Verifying result..."
- Cancel support if appropriate
- Spinner or animation during wait

## Phase 3: Rich Status Model

**Problem:** Current status is a single `CapsState` enum (Enabled/Disabled/Unknown). Linux has multiple overlapping keyboard config layers (system, session, runtime) that can disagree. A single boolean flattens this complexity and can be misleading.

**Solution — Data model:**
```cpp
enum class CapsScope { Session, System, Console, Mixed, Unknown };
enum class Confidence { High, Medium, Low };

struct ProbeResult {
    bool detected = false;
    bool capsDisabled = false;
    QString source;       // e.g. "GNOME gsettings", "localectl", "KDE kxkbrc"
    QString detail;
    Confidence confidence = Confidence::Low;
};

struct ProbeBundle {
    std::optional<ProbeResult> session;
    std::optional<ProbeResult> system;
    std::optional<ProbeResult> runtime;
};

struct ResolvedCapsStatus {
    CapsState primaryState = CapsState::Unknown;
    QString primarySource;
    QString secondaryDetail;
    bool sourcesDisagree = false;
};
```

**Resolution rules:**
1. If session probe succeeds, use as primary state
2. If session fails but system probe succeeds, show system result labeled as "system default"
3. If they disagree, surface the disagreement (tooltip or secondary label)

**UI improvements:**
- Show source: "Disabled (GNOME session)" or "Enabled (system keyboard config)"
- Show disagreement: "System default differs" as subtle secondary text
- Tooltip with full detail from all probes

## Phase 4: Backend Abstraction

**Long-term architecture for maintainability:**

```
ToolsWidget (UI only)
  -> CapsController (orchestrates apply + verify)
       -> SessionBackend (desktop-specific)
       |    -> GnomeBackend
       |    -> KdeBackend
       |    -> GenericDesktopBackend
       -> SystemBackend (privileged helper)
       -> StatusResolver (combines probes -> honest status)
```

## Other Deferred Items

- **QSettings for kxkbrc parsing** (Gemini) — Use `QSettings` with `IniFormat` to read specific `[Layout]/Options` key instead of raw string `contains("caps:none")`. Avoids false positives from commented-out entries.
- **Runtime detection via `setxkbmap -query`** (Grok) — Check actual X11 runtime state, not just config files. Most accurate for "what is happening right now" but X11-only.
- **Async status probes** (Gemini) — Run `localectl`/`gsettings` probes via async QProcess signals instead of blocking `waitForFinished`. Currently acceptable since probes run via `QTimer::singleShot(0)` after UI renders and complete in <100ms typically.
