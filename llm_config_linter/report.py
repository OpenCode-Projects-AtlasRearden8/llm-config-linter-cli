"""Human-facing output: per-issue fix-me lines and the all-clear card."""
import io

SEVERITY_ORDER = {"error": 0, "warn": 1, "info": 2}


def summarize(issues):
    counts = {"error": 0, "warn": 0, "info": 0}
    for i in issues:
        counts[i.severity] = counts.get(i.severity, 0) + 1
    return counts


def sort_issues(issues):
    return sorted(issues, key=lambda i: (SEVERITY_ORDER.get(i.severity, 9), i.check, i.where, i.message))


def render_issues(issues):
    lines = []
    for issue in sort_issues(issues):
        lines.append(issue.format())
        lines.append("")
    return "\n".join(lines).rstrip()


def _pad(s, width):
    return s + " " * max(width - len(s), 0)


def summary_card(rows, title="config summary"):
    """Render a small ASCII summary card. `rows` is [(label, value), ...]."""
    label_w = max((len(l) for l, _ in rows), default=0)
    value_w = max((len(str(v)) for _, v in rows), default=len(title))
    label_w = max(label_w, len(title) - 2)
    inner = label_w + 2 + value_w
    top = "+" + "-" * inner + "+"
    out = [top, "| " + _pad(title, inner - 2) + " |", top]
    for label, value in rows:
        out.append("| " + _pad(label, label_w) + "  " + _pad(str(value), value_w) + " |")
    out.append(top)
    return "\n".join(out)


def render_report(filename, kind, issues, cfg, files_scanned=None, plain=False):
    out = io.StringIO()
    counts = summarize(issues)

    if plain:
        out.write(f"{filename}\n")
    else:
        kind_label = {"yaml": "YAML", "toml": "TOML"}.get(kind, kind.upper())
        out.write(f"\n== {filename} ({kind_label}) ==\n")

    if counts["error"] or counts["warn"]:
        counts_line = (
            f"{counts['error']} error(s), {counts['warn']} warning(s)"
            + (f", {counts['info']} info" if counts["info"] else "")
        )
        out.write(f"\n{counts_line} found:\n\n")
        out.write(render_issues(issues))
        out.write("\n")
        if plain:
            return out.getvalue()
        rows = _rows_from_cfg(cfg, files_scanned)
        out.write(summary_card(rows, title="config summary (as parsed)"))
        out.write("\n")
        return out.getvalue()

    # all clear
    out.write("NO ISSUES: your config looks healthy.\n\n")
    rows = _rows_from_cfg(cfg, files_scanned)
    if counts["info"]:
        n_info = counts["info"]
        rows.append(("info notes", f"{n_info} (see below)"))
    out.write(summary_card(rows))
    if counts["info"]:
        out.write("\ninformational notes:\n")
        for issue in issues:
            if issue.severity == "info":
                out.write(f"  - {issue.message}\n")
    return out.getvalue()


def _first_of(cfg, *names):
    from .linter import get_first

    found = get_first(cfg, *names)
    return found[1] if found is not None else None


def _rows_from_cfg(cfg, files_scanned=None):
    rows = []
    base = _first_of(cfg, "base_url", "baseurl", "endpoint", "url", "api_base")
    rows.append(("base_url", str(base) if base is not None else "(not set)"))
    model = _first_of(cfg, "model", "model_name", "llm")
    rows.append(("model", str(model) if model is not None else "(not set)"))
    timeout = _first_of(
        cfg, "timeout", "timeout_seconds", "request_timeout", "read_timeout"
    )
    rows.append(("timeout", str(timeout) if timeout is not None else "(not set)"))
    temp = _first_of(cfg, "temperature", "temp")
    rows.append(("temperature", str(temp) if temp is not None else "(not set)"))

    api_key = _first_of(cfg, "api_key", "apikey", "token", "secret", "password")
    if api_key in (None, ""):
        key_status = "not set (fine for local servers)"
    elif isinstance(api_key, str) and api_key.startswith("$"):
        key_status = f"env-var ({api_key})"
    else:
        key_status = "hard-coded value (see warnings)"
    rows.append(("api_key", key_status))
    if files_scanned:
        rows.append(("files scanned", ", ".join(str(f) for f in files_scanned)))
    return rows
