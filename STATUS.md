# STATUS.md - llm-config-lint

## What was built

`llm-config-lint` is an offline CLI that sanity-checks the config files
your local-AI tools share (YAML or TOML). It is deliberately static: it
reads files and checks shapes; it never contacts an endpoint.

Package layout:

- `llm_config_linter/loader.py` - YAML/TOML loading (+ key
  normalization so `base-url` and `base_url` are treated the same)
- `llm_config_linter/linter.py` - all checks + the `Issue` model with
  per-problem fix-me snippets
- `llm_config_linter/report.py` - issue rendering + ASCII summary card
- `llm_config_linter/cli.py` - argparse CLI (`llm-config-lint`),
  exit codes 0/1/2, `--json` output
- `tests/` - 76 pytest tests with config fixtures in `tests/fixtures/`

### Checks implemented

1. **base_url shape** - missing scheme, non-http(s) schemes, https on a
   local host, local host without a port, Ollama endpoints missing the
   OpenAI-compatible `/v1` route, empty/wrong-typed values, whitespace,
   keys embedded in URLs; searches nested sections.
2. **Pasted API keys** - known key shapes (OpenAI `sk-...`, Groq
   `gsk_...`, Hugging Face `hf_...`, xAI `xai-...`, AWS `AKIA...`,
   GitLab `glpat-...`, GitHub `ghp_...`) anywhere in the config,
   including non-key fields; hard-coded non-standard key values warn;
   `${ENV_VAR}` references pass clean. Detected keys are always
   redacted in output.
3. **Personal home paths** - `/home/<user>`, `/Users/<user>`,
   `C:\Users\<user>` in any string value.
4. **Model names** - empty, whitespace/spaces, URLs pasted into the
   model slot, unusual characters, a lowercase-case info note for
   local model ids.
5. **Timeout** - bare seconds expected; flags quoting "60", "30000ms"
   style millis, sub-1s values, values over 600s, `"2 min"` units.
6. **Temperature** - non-numeric types, values outside 0.0-2.0, info
   note above 1.0.
7. **File hygiene** - world-readable/world-writable permissions on
   config files, and a raw content scan for secret-shaped lines.
8. **Unknown settings** - info-level note for keys the linter doesn't
   recognize (typo'd settings are usually silently ignored).

Output: either a fix-me block per problem, or an all-clear message with
a config summary card (base_url, model, timeout, temperature, api_key
status, files scanned).

## How to run it

```bash
pip install .                       # from this folder (Python 3.10+)
llm-config-lint my-llm.yaml         # one file
llm-config-lint a.yaml b.toml       # several
llm-config-lint --json my-llm.yaml  # machine-readable
llm-config-lint --version
```

Exit codes: `0` clean (warnings don't fail), `1` errors found, `2`
file missing/unparseable.

## Verification results

- `python -m pytest tests -q` -> **76 passed** (tests cover the loader,
  every check, fixture files, file-permission states, and the CLI
  end-to-end including `--json`, exit codes and multi-file runs).
- `pip install .` builds and installs cleanly (non-editable wheel build
  via setuptools, no build isolation tricks beyond what pip provides);
  the installed `llm-config-lint` command ran sample configs correctly.
- Manual smoke tests: clean Ollama YAML/TOML -> all-clear card; messy
  config (`ws://` scheme, out-of-range temperature, `"500ms"` timeout,
  `/Users/dylan/...` path, pasted sample key) -> every expected check
  fired with fix-me snippets; broken YAML -> parse error with exit 2.

## Known gaps

- YAML anchors/aliases are resolved by the YAML parser, fine, but the
  linter keys on common setting names; deeply unusual schemas may be
  ignored (the unknown-setting info note helps here).
- Key-shape detection is pattern-based: brand-new key formats will not
  be recognized until added to `SECRET_PATTERNS` in
  `llm_config_linter/linter.py`.
- Permission checks run on Unix models (`chmod` suggestions); Windows
  ACLs are out of scope.
- No packaging beyond a plain `pip install .` (no PyPI publishing).
- Timeout unit parsing accepts `ms/s/s/m`; exotic formats (ISO-8601
  durations) are rejected with a fix-me suggestion.

## Housekeeping

- License: MIT, `Copyright (c) 2026 Asdale Dynamics, LLC` (LICENSE).
- README credits [Asdale Dynamics, LLC](https://dylanasdale.github.io).
- No secrets, API keys, or personal data in files: fixtures use an
  obviously fake sample string (`sk-sample-test-key-not-real-...`) and
  test-only paths.
