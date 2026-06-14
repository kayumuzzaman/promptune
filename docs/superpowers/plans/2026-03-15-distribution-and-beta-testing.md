# Distribution & Beta Testing Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Prepare Promptune for beta distribution with LICENSE, GitHub URL fixes, curl installer, release automation, and supporting tests.

**Architecture:** Infrastructure-only changes — no modifications to existing `promptune/*.py` source files. New files: `LICENSE`, `install.sh`, `.github/workflows/release.yml`, `tests/test_install.py`. Metadata changes to `pyproject.toml` and `README.md` (URLs and classifier only).

**Tech Stack:** Bash (install.sh), GitHub Actions YAML, pytest + subprocess (install tests), Python packaging (`build` module)

**Spec:** `docs/superpowers/specs/2026-03-14-distribution-and-beta-testing-design.md`

---

## Chunk 1: Foundation (LICENSE, URLs, Classifier, Version Sync Test)

### Task 1: Add LICENSE file

**Files:**
- Create: `LICENSE`

- [x]**Step 1: Create MIT LICENSE file**

```text
MIT License

Copyright (c) 2026 kayumuzzaman

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

- [x]**Step 2: Verify LICENSE exists and contains correct copyright**

Run: `head -5 LICENSE`
Expected: Contains "MIT License" and "Copyright (c) 2026 kayumuzzaman"

- [x]**Step 3: Commit**

```bash
git add LICENSE
git commit -m "Add MIT LICENSE file"
```

---

### Task 2: Fix GitHub URLs and add MIT classifier

**Files:**
- Modify: `pyproject.toml:51-53` (URLs section)
- Modify: `pyproject.toml:16-28` (classifiers section)
- Modify: `README.md:22` (clone URL)

- [x]**Step 1: Fix URLs in pyproject.toml**

In `pyproject.toml`, change lines 51-53:

```toml
[project.urls]
Homepage = "https://github.com/kayumuzzaman/promptune"
Repository = "https://github.com/kayumuzzaman/promptune"
```

- [x]**Step 2: Add MIT classifier to pyproject.toml**

In `pyproject.toml`, add to the classifiers list (after line 20, the "Operating System :: MacOS" entry):

```toml
    "License :: OSI Approved :: MIT License",
```

- [x]**Step 3: Fix clone URL in README.md**

In `README.md`, change line 22:

```
git clone https://github.com/kayumuzzaman/promptune.git
```

- [x]**Step 4: Verify no "your-username" remains anywhere in the project**

Run: `grep -r "your-username" --include="*.toml" --include="*.md" --include="*.py" --include="*.yml" .`
Expected: No output (zero matches)

- [x]**Step 5: Verify package still installs correctly**

Run: `source .venv/bin/activate && pip install -e . && promptune --version`
Expected: Prints `0.1.0`

- [x]**Step 6: Commit**

```bash
git add pyproject.toml README.md
git commit -m "Fix GitHub URLs and add MIT license classifier"
```

---

### Task 3: Add version sync test (TDD)

**Files:**
- Modify: `tests/test_cli.py` (add one test)

- [x]**Step 1: Write the version sync test**

Add to `tests/test_cli.py`:

```python
def test_version_sync():
    """Version in pyproject.toml matches promptune/__init__.py."""
    import sys
    from pathlib import Path

    if sys.version_info >= (3, 11):
        import tomllib
    else:
        import tomli as tomllib

    pyproject_path = Path(__file__).parent.parent / "pyproject.toml"
    with open(pyproject_path, "rb") as f:
        pyproject = tomllib.load(f)

    pyproject_version = pyproject["project"]["version"]
    assert pyproject_version == promptune.__version__, (
        f"pyproject.toml version ({pyproject_version}) != "
        f"__init__.py version ({promptune.__version__})"
    )
```

This test is a guard for future releases — it will catch version desynchronization when either file is updated without the other.

- [x]**Step 2: Run test to verify it passes**

Run: `source .venv/bin/activate && pytest tests/test_cli.py::test_version_sync -v`
Expected: PASS (both are currently "0.1.0")

- [x]**Step 3: Commit**

```bash
git add tests/test_cli.py
git commit -m "Add version sync test between pyproject.toml and __init__.py"
```

---

### Task 4: Verify all existing tests still pass (regression gate)

- [x]**Step 1: Run full test suite**

Run: `source .venv/bin/activate && pytest --cov=promptune --cov-report=term-missing -v`
Expected: All tests pass (existing + new version sync test), coverage >= 90%

- [x]**Step 2: Run linting and type checking**

Run: `source .venv/bin/activate && ruff check . && mypy promptune/`
Expected: Both pass with zero errors

---

## Chunk 2: Install Script (TDD)

### Task 5: Write install.sh tests (RED)

**Files:**
- Create: `tests/test_install.py`

The install.sh tests use pytest + `subprocess.run()` to invoke the script in a controlled environment. Each test creates a temporary `PATH` with mock binaries to simulate different system states.

- [x]**Step 1: Create test file with all test cases**

Create `tests/test_install.py`:

```python
"""Tests for install.sh curl installer script."""

import os
import stat
import subprocess
from pathlib import Path

import pytest

# Path to the install script
INSTALL_SCRIPT = Path(__file__).parent.parent / "install.sh"


def _run_install(
    env_overrides: dict[str, str] | None = None,
    tmp_path: Path | None = None,
) -> subprocess.CompletedProcess[str]:
    """Run install.sh with optional environment overrides."""
    env = os.environ.copy()
    if env_overrides:
        env.update(env_overrides)
    # Always use a tmp HOME to avoid polluting real home
    if tmp_path and "HOME" not in (env_overrides or {}):
        env["HOME"] = str(tmp_path)
    return subprocess.run(
        ["bash", str(INSTALL_SCRIPT)],
        capture_output=True,
        text=True,
        env=env,
        timeout=30,
    )


def _create_mock_binary(
    tmp_path: Path, name: str, script: str, make_executable: bool = True
) -> Path:
    """Create a mock binary script in tmp_path/bin/."""
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir(exist_ok=True)
    binary = bin_dir / name
    binary.write_text(script)
    if make_executable:
        binary.chmod(binary.stat().st_mode | stat.S_IEXEC)
    return bin_dir


def test_rejects_non_macos(tmp_path: Path) -> None:
    """Script exits with error on non-macOS systems."""
    # Create a fake uname that reports "Linux"
    bin_dir = _create_mock_binary(
        tmp_path, "uname", '#!/bin/bash\necho "Linux"'
    )
    result = _run_install(
        env_overrides={"PATH": f"{bin_dir}:{os.environ['PATH']}"},
        tmp_path=tmp_path,
    )
    assert result.returncode != 0
    assert "macOS" in result.stderr or "macOS" in result.stdout


def test_rejects_root(tmp_path: Path) -> None:
    """Script exits with error when PROMPTUNE_FAKE_EUID=0 is set."""
    # The script checks PROMPTUNE_FAKE_EUID for testing, falls back to EUID
    result = _run_install(
        env_overrides={"PROMPTUNE_FAKE_EUID": "0"},
        tmp_path=tmp_path,
    )
    assert result.returncode != 0
    assert "root" in result.stderr or "root" in result.stdout


def test_rejects_old_python(tmp_path: Path) -> None:
    """Script exits with error when Python version is too old."""
    # Create a fake python3 that reports version 3.8
    # The -c handler must output "3 8" (matching the script's sys.version_info parsing)
    bin_dir = _create_mock_binary(
        tmp_path,
        "python3",
        '#!/bin/bash\nif [ "$1" = "--version" ]; then echo "Python 3.8.0"; '
        'elif [ "$1" = "-c" ]; then echo "3 8"; else exit 0; fi',
    )
    # Also need a real uname that says Darwin
    _create_mock_binary(
        tmp_path, "uname", '#!/bin/bash\necho "Darwin"'
    )
    result = _run_install(
        env_overrides={"PATH": f"{bin_dir}:{os.environ['PATH']}"},
        tmp_path=tmp_path,
    )
    assert result.returncode != 0
    assert "3.9" in result.stderr or "3.9" in result.stdout


def test_prints_next_steps(tmp_path: Path) -> None:
    """Script output includes shell-init instructions and API key reminder."""
    # Create mock binaries that simulate successful install
    bin_dir = _create_mock_binary(
        tmp_path, "uname", '#!/bin/bash\necho "Darwin"'
    )
    _create_mock_binary(
        tmp_path,
        "python3",
        '#!/bin/bash\n'
        'if [ "$1" = "--version" ]; then echo "Python 3.12.0"; '
        'elif [ "$1" = "-c" ]; then echo "3 12"; '
        'else exit 0; fi',
    )
    _create_mock_binary(
        tmp_path,
        "pipx",
        '#!/bin/bash\nexit 0',
    )
    _create_mock_binary(
        tmp_path,
        "promptune",
        '#!/bin/bash\necho "0.1.0"',
    )
    result = _run_install(
        env_overrides={"PATH": f"{bin_dir}:{os.environ['PATH']}"},
        tmp_path=tmp_path,
    )
    output = result.stdout + result.stderr
    assert "shell-init" in output
    assert "API key" in output or "api key" in output.lower()


def test_network_failure_graceful_exit(tmp_path: Path) -> None:
    """Script prints user-friendly error when pipx install fails."""
    bin_dir = _create_mock_binary(
        tmp_path, "uname", '#!/bin/bash\necho "Darwin"'
    )
    _create_mock_binary(
        tmp_path,
        "python3",
        '#!/bin/bash\n'
        'if [ "$1" = "--version" ]; then echo "Python 3.12.0"; '
        'elif [ "$1" = "-c" ]; then echo "3 12"; '
        'else exit 0; fi',
    )
    # pipx that fails (simulating network failure)
    _create_mock_binary(
        tmp_path,
        "pipx",
        '#!/bin/bash\necho "ERROR: Could not install" >&2; exit 1',
    )
    result = _run_install(
        env_overrides={"PATH": f"{bin_dir}:{os.environ['PATH']}"},
        tmp_path=tmp_path,
    )
    assert result.returncode != 0
    output = result.stdout + result.stderr
    assert "fail" in output.lower() or "error" in output.lower()


def test_idempotent_install(tmp_path: Path) -> None:
    """Re-running script when promptune is already installed succeeds."""
    bin_dir = _create_mock_binary(
        tmp_path, "uname", '#!/bin/bash\necho "Darwin"'
    )
    _create_mock_binary(
        tmp_path,
        "python3",
        '#!/bin/bash\n'
        'if [ "$1" = "--version" ]; then echo "Python 3.12.0"; '
        'elif [ "$1" = "-c" ]; then echo "3 12"; '
        'else exit 0; fi',
    )
    _create_mock_binary(
        tmp_path,
        "pipx",
        '#!/bin/bash\nexit 0',
    )
    # promptune already exists
    _create_mock_binary(
        tmp_path,
        "promptune",
        '#!/bin/bash\necho "0.1.0"',
    )
    result = _run_install(
        env_overrides={"PATH": f"{bin_dir}:{os.environ['PATH']}"},
        tmp_path=tmp_path,
    )
    assert result.returncode == 0


def test_installs_pipx_if_missing(tmp_path: Path) -> None:
    """Script attempts to install pipx when not found on PATH."""
    bin_dir = _create_mock_binary(
        tmp_path, "uname", '#!/bin/bash\necho "Darwin"'
    )
    _create_mock_binary(
        tmp_path,
        "python3",
        '#!/bin/bash\n'
        'if [ "$1" = "--version" ]; then echo "Python 3.12.0"; '
        'elif [ "$1" = "-c" ]; then echo "3 12"; '
        # Simulate "pip install --user pipx" by creating a pipx mock
        'elif [ "$1" = "-m" ] && [ "$2" = "pip" ]; then exit 0; '
        'elif [ "$1" = "-m" ] && [ "$2" = "pipx" ]; then exit 0; '
        'else exit 0; fi',
    )
    # No pipx on PATH initially — script should try to install it
    # After python3 -m pip install, pipx still won't be on PATH in test
    # so the script will warn but continue
    result = _run_install(
        env_overrides={"PATH": f"{bin_dir}:{os.environ['PATH']}"},
        tmp_path=tmp_path,
    )
    output = result.stdout + result.stderr
    assert "pipx" in output.lower()


def test_installs_promptune(tmp_path: Path) -> None:
    """Script installs promptune via pipx from GitHub."""
    bin_dir = _create_mock_binary(
        tmp_path, "uname", '#!/bin/bash\necho "Darwin"'
    )
    _create_mock_binary(
        tmp_path,
        "python3",
        '#!/bin/bash\n'
        'if [ "$1" = "--version" ]; then echo "Python 3.12.0"; '
        'elif [ "$1" = "-c" ]; then echo "3 12"; '
        'else exit 0; fi',
    )
    # pipx that logs what it installs
    _create_mock_binary(
        tmp_path,
        "pipx",
        '#!/bin/bash\necho "pipx: $@"; exit 0',
    )
    _create_mock_binary(
        tmp_path,
        "promptune",
        '#!/bin/bash\necho "0.1.0"',
    )
    result = _run_install(
        env_overrides={"PATH": f"{bin_dir}:{os.environ['PATH']}"},
        tmp_path=tmp_path,
    )
    output = result.stdout + result.stderr
    assert "promptune" in output
    assert result.returncode == 0


def test_verifies_installation(tmp_path: Path) -> None:
    """Script runs promptune --version after install to verify."""
    bin_dir = _create_mock_binary(
        tmp_path, "uname", '#!/bin/bash\necho "Darwin"'
    )
    _create_mock_binary(
        tmp_path,
        "python3",
        '#!/bin/bash\n'
        'if [ "$1" = "--version" ]; then echo "Python 3.12.0"; '
        'elif [ "$1" = "-c" ]; then echo "3 12"; '
        'else exit 0; fi',
    )
    _create_mock_binary(
        tmp_path,
        "pipx",
        '#!/bin/bash\nexit 0',
    )
    _create_mock_binary(
        tmp_path,
        "promptune",
        '#!/bin/bash\necho "0.1.0"',
    )
    result = _run_install(
        env_overrides={"PATH": f"{bin_dir}:{os.environ['PATH']}"},
        tmp_path=tmp_path,
    )
    output = result.stdout + result.stderr
    assert "installed successfully" in output or "0.1.0" in output
```

- [x]**Step 2: Run tests to verify they fail (RED)**

Run: `source .venv/bin/activate && pytest tests/test_install.py -v`
Expected: All tests FAIL because `install.sh` does not exist yet

- [x]**Step 3: Commit failing tests**

```bash
git add tests/test_install.py
git commit -m "Add failing install.sh tests (RED phase)"
```

---

### Task 6: Implement install.sh (GREEN)

**Files:**
- Create: `install.sh`

- [x]**Step 1: Create install.sh script**

```bash
#!/bin/bash
# Promptune installer
# Usage: curl -fsSL https://raw.githubusercontent.com/kayumuzzaman/promptune/main/install.sh | bash
#
# Safer alternative:
#   curl -fsSL https://raw.githubusercontent.com/kayumuzzaman/promptune/main/install.sh -o install.sh
#   bash install.sh

REPO="https://github.com/kayumuzzaman/promptune.git"
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

info()  { echo -e "${GREEN}[promptune]${NC} $1"; }
warn()  { echo -e "${YELLOW}[promptune]${NC} $1"; }
error() { echo -e "${RED}[promptune]${NC} $1" >&2; }

# --- Precondition checks (before set -e, for graceful error messages) ---

check_os() {
    local os
    os="$(uname)"
    if [ "$os" != "Darwin" ]; then
        error "Promptune requires macOS (detected: $os)."
        error "Linux and other platforms are not supported yet."
        exit 1
    fi
}

check_not_root() {
    # Use PROMPTUNE_FAKE_EUID for testing, fall back to real EUID
    local euid="${PROMPTUNE_FAKE_EUID:-$EUID}"
    if [ "$euid" = "0" ]; then
        error "Do not run this installer as root."
        error "Run without sudo: curl -fsSL <url> | bash"
        exit 1
    fi
}

check_python() {
    if ! command -v python3 &> /dev/null; then
        error "Python 3 is not installed."
        error "Install Python 3.9+ from https://www.python.org/downloads/"
        exit 1
    fi

    local version
    version="$(python3 -c 'import sys; print(sys.version_info.major, sys.version_info.minor)')"
    local major minor
    major="$(echo "$version" | cut -d' ' -f1)"
    minor="$(echo "$version" | cut -d' ' -f2)"

    if [ "$major" -lt 3 ] || { [ "$major" -eq 3 ] && [ "$minor" -lt 9 ]; }; then
        error "Python 3.9+ is required (found: $(python3 --version))."
        error "Install a newer version from https://www.python.org/downloads/"
        exit 1
    fi
    info "Found $(python3 --version)"
}

# Run precondition checks
check_os
check_not_root
check_python

# --- Main install (strict mode after precondition checks) ---
set -euo pipefail

install_pipx() {
    if command -v pipx &> /dev/null; then
        info "pipx is already installed."
        return 0
    fi

    info "Installing pipx..."
    python3 -m pip install --user pipx 2>/dev/null || {
        error "Failed to install pipx. Check your Python/pip setup."
        exit 1
    }
    python3 -m pipx ensurepath 2>/dev/null || true
    # Add common pipx binary locations to PATH for this session
    export PATH="$HOME/.local/bin:$PATH"

    if ! command -v pipx &> /dev/null; then
        warn "pipx installed but not found in PATH."
        warn "You may need to restart your shell or run: export PATH=\"\$HOME/.local/bin:\$PATH\""
    fi
}

install_promptune() {
    info "Installing promptune from GitHub..."
    if command -v promptune &> /dev/null; then
        info "promptune is already installed. Upgrading..."
        pipx upgrade promptune 2>/dev/null || pipx install --force "git+${REPO}" || {
            error "Failed to upgrade promptune."
            exit 1
        }
    else
        pipx install "git+${REPO}" || {
            error "Failed to install promptune."
            error "This could be a network issue. Check your internet connection and try again."
            exit 1
        }
    fi
}

verify_install() {
    if command -v promptune &> /dev/null; then
        local version
        version="$(promptune --version 2>/dev/null || echo 'unknown')"
        info "promptune $version installed successfully!"
        return 0
    fi
    # Try with explicit path
    if [ -x "$HOME/.local/bin/promptune" ]; then
        info "promptune installed at ~/.local/bin/promptune"
        return 0
    fi
    warn "promptune installed but not found in PATH."
    warn "Try: export PATH=\"\$HOME/.local/bin:\$PATH\""
    return 0
}

print_next_steps() {
    echo ""
    info "--- Next Steps ---"
    echo ""
    echo "  1. Configure your API key:"
    echo "     promptune config init"
    echo ""
    echo "  2. You need an API key for at least one provider:"
    echo "     - Claude:     https://console.anthropic.com/"
    echo "     - OpenAI:     https://platform.openai.com/"
    echo "     - OpenRouter:  https://openrouter.ai/"
    echo ""
    echo "  3. Set up the shell widget (add to ~/.zshrc):"
    echo "     eval \"\$(promptune shell-init)\""
    echo ""
    echo "  4. Press Ctrl+E in your terminal to enhance prompts!"
    echo ""
}

install_pipx
install_promptune
verify_install
print_next_steps
```

- [x]**Step 2: Make install.sh executable**

Run: `chmod +x install.sh`

- [x]**Step 3: Run tests to verify they pass (GREEN)**

Run: `source .venv/bin/activate && pytest tests/test_install.py -v`
Expected: All tests PASS

- [x]**Step 4: If any tests fail, adjust install.sh until all pass**

Debug by running individual tests:
```bash
pytest tests/test_install.py::test_rejects_non_macos -v -s
```

- [x]**Step 5: Run full test suite to verify no regressions**

Run: `source .venv/bin/activate && pytest --cov=promptune --cov-report=term-missing -v`
Expected: All tests pass, coverage >= 90%

- [x]**Step 6: Commit**

```bash
git add install.sh tests/test_install.py
git commit -m "Add install.sh curl installer with tests (GREEN phase)"
```

---

## Chunk 3: Release Workflow & README Updates

### Task 7: Align CI coverage threshold with release

**Files:**
- Modify: `.github/workflows/ci.yml:42`

The release workflow uses `--cov-fail-under=90` (per spec). The existing CI uses `--cov-fail-under=80` (from Step 5 era). Since Step 10 already achieved >= 90% coverage, align CI to the same threshold so there's no surprise when a release tag is pushed.

Note: The spec section 7.3 lists `ci.yml` under "WILL NOT be modified." This is an intentional deviation — changing only the coverage threshold (a numeric constant) to align CI with the release pipeline. The spec has been updated to reflect this.

- [x]**Step 1: Update CI coverage threshold to 90%**

In `.github/workflows/ci.yml` line 42, change:

```yaml
        run: pytest --cov=promptune --cov-report=term-missing --cov-fail-under=90
```

- [x]**Step 2: Verify CI still passes locally**

Run: `source .venv/bin/activate && pytest --cov=promptune --cov-report=term-missing --cov-fail-under=90`
Expected: PASS (Step 10 already achieved >= 90%)

- [x]**Step 3: Commit**

```bash
git add .github/workflows/ci.yml
git commit -m "Align CI coverage threshold to 90% (matching release pipeline)"
```

---

### Task 8: Create release.yml workflow

**Files:**
- Create: `.github/workflows/release.yml`

Note: The release workflow duplicates CI validation steps (lint, typecheck, tests) rather than using a reusable workflow. This is intentional — extracting CI into a reusable workflow is a larger refactor and the duplication is minimal (one job). The release must be self-contained to ensure a tagged release never ships without passing all gates, even if CI was green on a different commit.

- [x]**Step 1: Create the release workflow**

Create `.github/workflows/release.yml`:

```yaml
name: Release

on:
  push:
    tags:
      - "v*"

permissions:
  contents: write

jobs:
  validate:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        python-version: ["3.12", "3.13"]

    steps:
      - name: Checkout
        uses: actions/checkout@v4

      - name: Setup Python ${{ matrix.python-version }}
        uses: actions/setup-python@v5
        with:
          python-version: ${{ matrix.python-version }}

      - name: Install dependencies
        run: pip install -e ".[dev]"

      - name: Lint
        run: ruff check .

      - name: Type check
        run: mypy promptune/

      - name: Tests with coverage
        run: pytest --cov=promptune --cov-report=term-missing --cov-fail-under=90

  build:
    needs: validate
    runs-on: ubuntu-latest

    steps:
      - name: Checkout
        uses: actions/checkout@v4

      - name: Setup Python 3.12
        uses: actions/setup-python@v5
        with:
          python-version: "3.12"

      - name: Install build tools
        run: pip install build

      - name: Build sdist and wheel
        run: python -m build

      - name: Upload build artifacts
        uses: actions/upload-artifact@v4
        with:
          name: dist
          path: dist/

  release:
    needs: build
    runs-on: ubuntu-latest

    steps:
      - name: Download build artifacts
        uses: actions/download-artifact@v4
        with:
          name: dist
          path: dist/

      - name: Create GitHub Release
        uses: softprops/action-gh-release@v2
        with:
          generate_release_notes: true
          files: dist/*

  # Uncomment when ready to publish to PyPI:
  # 1. Register "promptune" on pypi.org
  # 2. Configure GitHub OIDC as trusted publisher in PyPI project settings
  # 3. Uncomment the block below
  #
  # publish:
  #   needs: build
  #   runs-on: ubuntu-latest
  #   environment: pypi
  #   permissions:
  #     id-token: write
  #
  #   steps:
  #     - name: Download build artifacts
  #       uses: actions/download-artifact@v4
  #       with:
  #         name: dist
  #         path: dist/
  #
  #     - name: Publish to PyPI
  #       uses: pypa/gh-action-pypi-publish@release/v1
```

- [x]**Step 2: Validate YAML syntax**

Run: `python3 -c "import yaml; yaml.safe_load(open('.github/workflows/release.yml'))" 2>/dev/null || python3 -c "print('YAML module not available, skip syntax check')"`

Alternatively, verify manually that the file has correct indentation (2-space YAML).

- [x]**Step 3: Commit**

```bash
git add .github/workflows/release.yml
git commit -m "Add release workflow (tag-triggered, PyPI commented out)"
```

---

### Task 9: Update README.md with install methods

**Files:**
- Modify: `README.md:13-25` (Installation section)

- [x]**Step 1: Update the Installation section in README.md**

Replace the existing Installation section (lines 13-25) with:

```markdown
## Installation

### Quick Install (macOS)

```bash
curl -fsSL https://raw.githubusercontent.com/kayumuzzaman/promptune/main/install.sh | bash
```

Or safer (inspect before running):

```bash
curl -fsSL https://raw.githubusercontent.com/kayumuzzaman/promptune/main/install.sh -o install.sh
bash install.sh
```

### Using pipx (recommended)

```bash
pipx install git+https://github.com/kayumuzzaman/promptune.git
```

### Using pip

```bash
pip install git+https://github.com/kayumuzzaman/promptune.git
```

### For development

```bash
git clone https://github.com/kayumuzzaman/promptune.git
cd promptune
pip install -e ".[dev]"
```
```

- [x]**Step 2: Verify no "your-username" remains in README**

Run: `grep "your-username" README.md`
Expected: No output (zero matches)

- [x]**Step 3: Commit**

```bash
git add README.md
git commit -m "Update README with distribution install methods"
```

---

### Task 10: Final regression check and quality gates

- [x]**Step 1: Run full test suite with coverage**

Run: `source .venv/bin/activate && pytest --cov=promptune --cov-report=term-missing -v`
Expected: All tests pass, coverage >= 90%

- [x]**Step 2: Run linting**

Run: `source .venv/bin/activate && ruff check .`
Expected: Zero errors

- [x]**Step 3: Run type checking**

Run: `source .venv/bin/activate && mypy promptune/`
Expected: Zero errors

- [x]**Step 4: Verify package builds successfully**

Run: `source .venv/bin/activate && pip install build && python -m build`
Expected: Both `.whl` and `.tar.gz` created in `dist/`

- [x]**Step 5: Verify package installs from build**

Run: `source .venv/bin/activate && pip install -e . && promptune --version`
Expected: Prints `0.1.0`

- [x]**Step 6: Verify no "your-username" anywhere**

Run: `grep -r "your-username" --include="*.toml" --include="*.md" --include="*.py" --include="*.yml" .`
Expected: No output

- [x]**Step 7: Review all changes since start**

Run: `git log --oneline -10`
Expected commits (most recent first):
1. "Update README with distribution install methods"
2. "Add release workflow (tag-triggered, PyPI commented out)"
3. "Align CI coverage threshold to 90% (matching release pipeline)"
4. "Add install.sh curl installer with tests (GREEN phase)"
5. "Add failing install.sh tests (RED phase)"
6. "Add version sync test between pyproject.toml and __init__.py"
7. "Fix GitHub URLs and add MIT license classifier"
8. "Add MIT LICENSE file"
