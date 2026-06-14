# Security Policy

Promptune runs locally and stores provider API keys in your local config
(`~/.config/promptune/config.toml`) — never in the repository or in telemetry.

## Reporting a vulnerability

Please report security issues **privately** via GitHub's
[private vulnerability reporting](https://github.com/kayumuzzaman/promptune/security/advisories/new)
rather than opening a public issue. We aim to respond within 7 days.

Areas worth scrutiny:

- the system daemon (clipboard access, global hotkey, macOS Accessibility)
- the auto-enhance hook (reads submitted prompts)
- the secret sanitizer in context collection (`promptune/context/sanitizer.py`)
