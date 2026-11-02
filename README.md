# llm-config-lint

Sanity-check the config files your local-AI tools share - before they
waste your evening. It reads simple YAML/TOML configs, validates the
things that break silently (wrong `base_url` shape, typo'd model names,
timeout in the wrong unit, temperature out of range), and flags the
things that shouldn't be there at all (accidentally pasted API keys,
your personal home paths, files that are world-readable).

Everything runs offline and stays on your machine. No pings, no
installers, no telemetry.

Brought to you by [Asdale Dynamics, LLC](https://dylanasdale.github.io)
- the folks who explain AI like a friend would.

## What it checks

| Check | What it catches |
| --- | --- |
| `base_url` shape | Missing scheme, `ftp://` instead of `http(s)://`, `https://localhost`, missing port, Ollama needing the `/v1` route |
| API keys | Keys pasted into any field (`sk-...`, `gsk_...`, `hf_...`, `ghp_...`, AWS `AKIA...`), hard-coded non-environment values |
| Home paths | `/home/dylan/...`, `/Users/dylan/...`, `C:\Users\dylan\...` - configs that break on other machines and leak your username |
| Model name | Empty, spaces, a URL pasted into the model slot, unusual characters |
| Timeout | Quoted numbers, milliseconds vs seconds, sub-1s values, caps over 10 minutes |
| Temperature | Outside the supported 0.0-2.0 range, values above 1.0 that get incoherent |
| File hygiene | Config files that are world-readable or world-writable, raw secrets sitting in file text |
| Unknown keys | Setting names most tools would silently ignore |

Every problem comes with a **fix-me snippet** - a small block of YAML
you can paste in (or adapt) to make the warning go away.

## Install

```bash
pip install .                # from this folder
# or for hacking on it:
pip install -e .[dev]
```

Requires Python 3.10+.

## Run it

```bash
# one file
llm-config-lint my-llm.yaml

# several at once
llm-config-lint ~/.config/myapp/config.yaml ./ollama.toml

# machine-readable output for scripts and CI
llm-config-lint --json my-llm.yaml
```

### All clear

```
== ollama.toml (TOML) ==

NO ISSUES: your config looks healthy.

+--------------------------------------+
| config summary                       |
+--------------------------------------+
| end          http://127.0.0.1:11434/v1 |
| model        mistral:7b               |
...
```

### A fix-me example

```
[error] pasted-secret: api_key contains a Hugging Face token (hf_Ab12...zX).
Secrets in config files get committed and copied - reference an
environment variable instead.
    fix-me:
      api_key: ${MY_API_KEY}
```

## Exit codes

- `0` - clean (warnings don't fail the run)
- `1` - at least one error found
- `2` - file not found or unparseable

## Scope

This linter is deliberately **static**: it reads files and checks
shapes. It never contacts your endpoints. If you want live "is my
server up?" behavior, that's the job of an endpoint health checker;
if you want disk-usage triage for downloaded models, that's a disk
doctor. One tool, one job.

## Developing

```bash
pip install -e .[dev]
pytest          # the test suite uses small YAML/TOML fixtures in tests/fixtures
```

## License

MIT - see [LICENSE](LICENSE). Copyright (c) 2026 Asdale Dynamics, LLC.

## Privacy note

This tool never sends anywhere anything you didn't already have on
disk, and it never prints full secrets: detected keys are always
redacted to their first few characters.
