# MyCCPlugins

Declarative Claude Code plugin/skill manager. Clone this repo on any machine or
container and run one command to get your full setup.

## Quick start

```bash
git clone <this-repo>
cd MyCCPlugins
./install.sh
```

## How it works

Edit `ccplugins.yml` to declare what you want installed, then run `./install.sh`
(or `python3 sync.py`) to apply.

```
MyCCPlugins/
├── ccplugins.yml        # declarative config — edit this
├── install.sh           # one-command entry point
├── sync.py              # sync logic (no external deps)
└── skills/              # your custom slash-command .md files
    └── example-commit.md
```

## ccplugins.yml reference

```yaml
# Custom plugin marketplaces (optional)
marketplaces:
  - name: my-org-plugins
    source: myorg/claude-plugins   # GitHub owner/repo

# Plugins from any registered marketplace
plugins:
  - name: feature-dev
    scope: user              # user (default) | project | local
  - name: code-review
    marketplace: claude-plugins-official  # optional, explicit marketplace

# Custom skills from this repo → installed to ~/.claude/commands/
skills:
  - path: skills/my-workflow.md
    scope: user              # user → ~/.claude/commands/
                             # project → .claude/commands/ (current dir)

# Settings merged into ~/.claude/settings.json (other keys untouched)
settings:
  model: opusplan
```

## Writing custom skills

A skill is a Markdown file that becomes a `/slash-command`. Create a `.md` file
in `skills/`, describe the task in plain language, then add it to `ccplugins.yml`
under `skills:`.

See `skills/example-commit.md` for a template.

## Syncing

The script is fully **idempotent** — running it multiple times is safe. It only
installs what is missing and skips what is already up to date.

To pull the latest changes and re-sync on a device:

```bash
git pull && ./install.sh
```
