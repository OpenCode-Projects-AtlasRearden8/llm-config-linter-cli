"""CLI entry point for llm-config-lint."""
import argparse
import os
import sys

from . import __version__
from .linter import (
    Issue,
    check_api_key,
    check_base_url,
    check_file_permissions,
    check_file_secret_free,
    check_home_paths,
    check_model,
    check_temperature,
    check_timeout,
    check_unknown_keys,
)
from .loader import ConfigParseError, load_config
from .report import render_report, summarize


def lint_file(path):
    """Run all checks against one config file.

    Returns (issues, cfg, kind); on a parse error cfg and kind are None
    and the issues list holds a single 'parse' error.
    """
    issues = []
    try:
        cfg, kind = load_config(path)
    except ConfigParseError as e:
        return (
            [
                Issue(
                    "error",
                    "parse",
                    str(e),
                    "# fix the syntax above so the file loads",
                    str(path),
                )
            ],
            None,
            None,
        )

    issues.extend(check_base_url(cfg))
    issues.extend(check_model(cfg))
    issues.extend(check_temperature(cfg))
    issues.extend(check_timeout(cfg))
    issues.extend(check_api_key(cfg))
    issues.extend(check_home_paths(cfg))
    issues.extend(check_unknown_keys(cfg))
    issues.extend(check_file_permissions(path))
    issues.extend(check_file_secret_free(path))

    return issues, cfg, kind


def main(argv=None):
    parser = argparse.ArgumentParser(
        prog="llm-config-lint",
        description=(
            "Sanity-check the config files your local-AI tools share "
            "(OpenAI-compatible endpoints, Ollama, model names, timeouts, "
            "temperature, and file hygiene). Fully offline."
        ),
    )
    parser.add_argument("configs", nargs="+", help="YAML or TOML config file(s) to lint")
    parser.add_argument(
        "--json", action="store_true", help="machine-readable output (issues only)"
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    parser.add_argument(
        "-V", action="store_true", help="same as --version",
    )
    args = parser.parse_args(argv)

    if args.V:
        print(f"llm-config-lint {__version__}")
        return 0

    exit_code = 0
    json_out = []
    for cfg_path in args.configs:
        path = os.path.abspath(cfg_path)
        if not os.path.exists(path):
            print(f"error: file not found: {cfg_path}")
            exit_code = 2
            continue
        issues, cfg, kind = lint_file(path)
        counts = summarize(issues)
        if args.json:
            json_out.append(
                {
                    "file": path,
                    "issues": [
                        {
                            "severity": i.severity,
                            "check": i.check,
                            "where": i.where,
                            "message": i.message,
                            "fix": i.fix,
                        }
                        for i in issues
                    ],
                }
            )
        else:
            files_scanned = [os.path.basename(path)] if os.path.exists(path) else []
            print(
                render_report(os.path.basename(path), kind, issues, cfg, files_scanned)
            )
        if counts["error"]:
            exit_code = 1
        # warnings/informational notes don't fail the run by default

    if args.json:
        import json

        print(json.dumps(json_out, indent=2))

    return exit_code


if __name__ == "__main__":
    sys.exit(main())
