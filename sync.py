#!/usr/bin/env python3
"""
Claude Code plugin/skill sync tool.
Reads ccplugins.yml and installs everything on the current machine.
"""

import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

# ── Minimal YAML parser (no external deps) ───────────────────────────────────

def parse_yaml(text: str) -> dict:
    """
    Parse the subset of YAML used in ccplugins.yml:
      - top-level mapping keys
      - sequences of mappings (plugins, skills, marketplaces)
      - sequences of scalars
      - simple scalar mappings (settings)
    Comments and blank lines are ignored.
    """
    lines = []
    for raw in text.splitlines():
        stripped = raw.rstrip()
        # drop comment-only lines but keep inline-comment removal for values
        code = stripped.split("#")[0].rstrip()
        if code.strip() == "":
            continue
        lines.append(code)

    root: dict = {}
    i = 0

    def indent(line: str) -> int:
        return len(line) - len(line.lstrip())

    def parse_scalar(s: str):
        s = s.strip().strip('"').strip("'")
        return s

    while i < len(lines):
        line = lines[i]
        ind = indent(line)
        if ind != 0:
            i += 1
            continue  # should not happen at root level
        m = re.match(r'^(\w[\w-]*):\s*(.*)', line)
        if not m:
            i += 1
            continue
        key = m.group(1)
        rest = m.group(2).strip()
        if rest:
            root[key] = parse_scalar(rest)
            i += 1
            continue
        # look ahead for children
        i += 1
        children_lines = []
        while i < len(lines) and indent(lines[i]) > 0:
            children_lines.append(lines[i])
            i += 1
        if not children_lines:
            root[key] = None
            continue
        # decide: list or mapping
        if children_lines[0].lstrip().startswith("-"):
            root[key] = parse_sequence(children_lines)
        else:
            root[key] = parse_mapping(children_lines)

    return root


def parse_mapping(lines: list) -> dict:
    result = {}
    for line in lines:
        m = re.match(r'\s+(\w[\w-]*):\s*(.*)', line)
        if m:
            k = m.group(1)
            v = m.group(2).strip().strip('"').strip("'")
            result[k] = v
    return result


def parse_sequence(lines: list) -> list:
    result = []
    current: dict | None = None
    for line in lines:
        m_item = re.match(r'(\s*)-\s*(.*)', line)
        if m_item:
            rest = m_item.group(2).strip()
            if ":" in rest:
                # - key: value  (first field of a mapping item)
                k, _, v = rest.partition(":")
                current = {k.strip(): v.strip().strip('"').strip("'")}
                result.append(current)
            else:
                # - scalar
                current = None
                result.append(rest.strip('"').strip("'"))
        else:
            # continuation of current mapping item
            m_kv = re.match(r'\s+(\w[\w-]*):\s*(.*)', line)
            if m_kv and isinstance(current, dict):
                k = m_kv.group(1)
                v = m_kv.group(2).strip().strip('"').strip("'")
                current[k] = v
    return result


# ── Helpers ───────────────────────────────────────────────────────────────────

CLAUDE_DIR = Path.home() / ".claude"
COLOR = {
    "green": "\033[32m",
    "yellow": "\033[33m",
    "red": "\033[31m",
    "cyan": "\033[36m",
    "reset": "\033[0m",
    "bold": "\033[1m",
}


def c(color: str, text: str) -> str:
    return f"{COLOR[color]}{text}{COLOR['reset']}"


def run(cmd: list[str], check=True) -> subprocess.CompletedProcess:
    print(c("cyan", f"  $ {' '.join(cmd)}"))
    result = subprocess.run(cmd, capture_output=False, text=True)
    if check and result.returncode != 0:
        print(c("red", f"  command failed (exit {result.returncode})"))
    return result


# ── Steps ─────────────────────────────────────────────────────────────────────

def sync_marketplaces(marketplaces: list):
    if not marketplaces:
        return
    print(c("bold", "\n[1/4] Marketplaces"))
    # Get already-registered marketplace names
    result = subprocess.run(
        ["claude", "plugin", "marketplace", "list"],
        capture_output=True, text=True
    )
    registered = set(re.findall(r'^\s*❯\s+(\S+)', result.stdout, re.MULTILINE))

    for mp in marketplaces:
        name = mp.get("name", "")
        source = mp.get("source", "")
        if not name or not source:
            print(c("yellow", f"  skip: invalid marketplace entry {mp}"))
            continue
        if name in registered:
            print(f"  {c('green', '✓')} {name} already registered")
        else:
            print(f"  adding marketplace {c('cyan', name)} …")
            run(["claude", "plugin", "marketplace", "add", source])


def sync_plugins(plugins: list) -> list[str]:
    """Returns list of setup reminders for newly-installed plugins."""
    reminders: list[str] = []
    if not plugins:
        return reminders
    print(c("bold", "\n[2/4] Plugins"))

    # Read installed state
    installed_json = CLAUDE_DIR / "plugins" / "installed_plugins.json"
    installed: dict = {}
    if installed_json.exists():
        try:
            data = json.loads(installed_json.read_text())
            installed = data.get("plugins", {})
        except Exception:
            pass

    for plugin in plugins:
        if isinstance(plugin, str):
            name, marketplace, scope, setup = plugin, None, "user", None
        else:
            name = plugin.get("name", "")
            marketplace = plugin.get("marketplace")
            scope = plugin.get("scope", "user")
            setup = plugin.get("setup")  # optional post-install slash command

        if not name:
            continue

        # Build the install target
        target = f"{name}@{marketplace}" if marketplace else name

        # Check if already installed at this scope
        already = any(
            name in k and any(e.get("scope") == scope for e in entries)
            for k, entries in installed.items()
        )
        if already:
            print(f"  {c('green', '✓')} {target} ({scope}) already installed")
        else:
            print(f"  installing {c('cyan', target)} (scope={scope}) …")
            result = run(["claude", "plugin", "install", target, "--scope", scope])
            if result.returncode == 0 and setup:
                reminders.append(f"{name}: run {c('cyan', setup)} in Claude Code to finish setup")

    return reminders


def sync_skills(skills: list, config_dir: Path):
    if not skills:
        return
    print(c("bold", "\n[3/4] Skills"))

    for skill in skills:
        if isinstance(skill, str):
            src_rel, scope = skill, "user"
        else:
            src_rel = skill.get("path", "")
            scope = skill.get("scope", "user")

        if not src_rel:
            continue

        src = (config_dir / src_rel).resolve()
        if not src.exists():
            print(c("yellow", f"  skip: {src_rel} not found"))
            continue

        if scope == "user":
            dest_dir = CLAUDE_DIR / "commands"
        else:
            dest_dir = Path.cwd() / ".claude" / "commands"

        dest_dir.mkdir(parents=True, exist_ok=True)
        dest = dest_dir / src.name

        if dest.exists() and dest.read_bytes() == src.read_bytes():
            print(f"  {c('green', '✓')} {src.name} ({scope}) up to date")
        else:
            shutil.copy2(src, dest)
            print(f"  {c('green', '✔')} {src.name} → {dest}")


def sync_settings(settings: dict):
    if not settings:
        return
    print(c("bold", "\n[4/4] Settings"))

    settings_path = CLAUDE_DIR / "settings.json"
    current: dict = {}
    if settings_path.exists():
        try:
            current = json.loads(settings_path.read_text())
        except Exception:
            pass

    changed = False
    for k, v in settings.items():
        if current.get(k) == v:
            print(f"  {c('green', '✓')} {k} = {v!r}")
        else:
            print(f"  {c('green', '✔')} {k}: {current.get(k)!r} → {v!r}")
            current[k] = v
            changed = True

    if changed:
        settings_path.write_text(json.dumps(current, indent=2) + "\n")


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    config_path = Path(__file__).parent / "ccplugins.yml"
    if not config_path.exists():
        print(c("red", f"Config not found: {config_path}"))
        sys.exit(1)

    raw = config_path.read_text()
    cfg = parse_yaml(raw)

    print(c("bold", f"Claude Code sync  •  config: {config_path}"))

    sync_marketplaces(cfg.get("marketplaces") or [])
    reminders = sync_plugins(cfg.get("plugins") or [])
    sync_skills(cfg.get("skills") or [], config_path.parent)
    sync_settings(cfg.get("settings") or {})

    print(c("green", "\nDone."))

    if reminders:
        print(c("bold", "\nNext steps (run inside Claude Code):"))
        for note in reminders:
            print(f"  • {note}")


if __name__ == "__main__":
    main()
