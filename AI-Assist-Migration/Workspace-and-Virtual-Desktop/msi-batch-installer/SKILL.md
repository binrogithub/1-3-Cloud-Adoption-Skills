---
name: msi-batch-installer
description: Install a set of .msi files silently via msiexec with logging, exit-code decoding, and summary reporting. Provides both CMD batch and PowerShell scripts.
---

# MSI Batch Installer

Scripts for installing multiple `.msi` packages on Windows via `msiexec.exe` with full logging, exit-code interpretation, and pass/fail summaries.

## msiexec Key Flags

| Flag | Meaning |
|------|---------|
| `/i` | Install |
| `/x` | Uninstall |
| `/qn` | Fully silent (no UI) |
| `/qb` | Basic UI (progress bar only) |
| `/L*V` | Verbose log to file |
| `/norestart` | Suppress reboot |
| `PROPERTY=value` | Pass public MSI property at install time |

## Critical Exit Codes

| Code | Meaning |
|------|---------|
| 0 | Success |
| 1602 | User cancelled |
| 1603 | Fatal error (usually permissions or locked files) |
| 1618 | Another installation already running |
| 1619 | MSI file could not be opened (missing/corrupt) |
| 1638 | Another version already installed |
| 3010 | Success — reboot required |

Full list: https://learn.microsoft.com/en-us/windows/win32/msi/error-codes

## Usage — CMD

```cmd
REM Install all .msi in current directory (silent)
install-msi.cmd

REM Install all .msi in a specific directory
install-msi.cmd "C:\Packages"

REM Install specific files
install-msi.cmd app1.msi app2.msi
```

**Configuration** (edit inside the script):
- `LOGDIR` — log output directory (default: `%TEMP%\msi-install-logs`)
- `UI_MODE` — `/qn` (silent) or `/qb` (basic UI)
- `EXTRA_PROPS` — MSI public properties, e.g. `ACCEPT_EULA=1`

## Usage — PowerShell

```powershell
# Install all .msi in current directory
.\install-msi.ps1

# Install specific files
.\install-msi.ps1 -Path "C:\Packages\myapp.msi","C:\Packages\other.msi"

# Install from a directory with basic UI and properties
.\install-msi.ps1 -Path "C:\Packages" -UiMode basic -Properties @{ ACCEPT_EULA = '1' }

# Stop on first failure
.\install-msi.ps1 -ContinueOnError:$false
```

**Parameters:**
- `-Path` — directory or file(s). Omit = current dir.
- `-UiMode` — `silent` (default), `basic`, or `full`
- `-NoReboot` — suppress reboot (default: on)
- `-LogDir` — log directory (default: `$env:TEMP\msi-install-logs`)
- `-Properties` — hashtable of MSI public properties
- `-ContinueOnError` — keep going after failures (default: on)

## Requirements

- **Must run as Administrator** — MSI installs fail with 1603 otherwise.
- Only one `msiexec` install can run at a time (error 1618 if concurrent).
- Scripts wait for each MSI to finish before starting the next.

## Pitfalls

1. **CMD `else if` inside `for` blocks** — CMD does not support `else if` chains inside parenthesized `for` blocks. Use `call :subroutine` instead.
2. **CMD labels inside `if/else` blocks** — Labels cannot be inside `if/else` parenthesized blocks. Use `goto` to jump to labeled sections outside the blocks.
3. **CMD parentheses in `echo` inside `if` blocks** — Escape them as `^( ^)`.
4. **CMD `!var!.log` with dot-stripped names** — Use `!MSI_NAME:.=_!_` to insert a literal underscore separator.
5. **CMD date/time locale issues** — Use `!date:~10,4!!date:~4,2!!date:~7,2!` for `YYYY MM DD` on US-locale Windows, and strip slashes with `!TIMESTAMP:/=!`.
6. **Directory detection** — Use `if exist "%ARG1%\*"` to check if a path is a directory.
7. **PowerShell `$args` is reserved** — Use `$argList` or similar for custom argument strings.
8. **Em dashes in PowerShell** — Use ASCII hyphens (-) instead.
9. **Log file paths** — Each install gets a unique log file named `<MSIname>_<timestamp>.log`.
10. **Error 1618** — If another MSI install is running, wait for it to finish.
11. **Error 1625** — "System policy prevents installation" — can mean the product is already installed AND running non-elevated, or a group policy blocks it.
12. **UAC elevation from bash** — PowerShell backtick line continuations are eaten by bash. Write a helper `.ps1` script and call it with `-File` instead of `-Command`.
13. **Capturing elevated output** — `Start-Process -Verb RunAs` opens a new console whose output is not captured. Redirect inside the elevated process.

## Elevation Helpers

Both scripts require Administrator rights. Helper scripts to launch elevated:

**PowerShell** (`run-elevated.ps1`):
```powershell
Start-Process -FilePath "powershell.exe" -ArgumentList @(
    "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command",
    "& { & '$scriptPath' -Path '$msiDir' *>&1 | Out-File '$outputFile' -Encoding UTF8; exit `$LASTEXITCODE }"
) -Verb RunAs -Wait
```

**CMD** (`run-elevated-cmd.ps1`):
```powershell
Start-Process -FilePath "cmd.exe" -ArgumentList @(
    "/c", "cd /d `"$msiDir`" & call `"$cmdScript`" > `"$outputFile`" 2>&1"
) -Verb RunAs -Wait
```

## Verification

After running, check:
1. Script exit code: `echo %ERRORLEVEL%` (CMD) or `$LASTEXITCODE` (PowerShell)
2. Summary table printed at the end
3. Log files in `%TEMP%\msi-install-logs\` for any failures
4. For error 1603, check the log for "Return value 3" entries
