"""Lint checks for local-AI config files.

Checks run per known setting (base_url, model, temperature, timeout,
api_key) plus file hygiene: no pasted secrets, not world-readable.
Every issue carries a fix-me snippet.
"""
import os
import re
import stat
from dataclasses import dataclass

# ---------------------------------------------------------------------------
# Patterns
# ---------------------------------------------------------------------------

SECRET_PATTERNS = [
    (re.compile(r"\bsk-[A-Za-z0-9_-]{20,}\b"), "OpenAI-style API key (sk-...)"),
    (re.compile(r"\bgsk_[A-Za-z0-9]{20,}\b"), "Groq API key (gsk_...)"),
    (re.compile(r"\bhf_[A-Za-z0-9]{20,}\b"), "Hugging Face token (hf_...)"),
    (re.compile(r"\bxai-[A-Za-z0-9]{20,}\b"), "xAI API key (xai-...)"),
    (re.compile(r"\bAKIA[0-9A-Z]{16}\b"), "AWS access key id (AKIA...)"),
    (re.compile(r"\bglpat-[A-Za-z0-9_-]{20,}\b"), "GitLab personal token (glpat-...)"),
    (re.compile(r"\bghp_[A-Za-z0-9]{30,}\b"), "GitHub personal token (ghp_...)"),
]

HOST_KEY_RE = re.compile(r"api[_-]?key|auth|token|secret|password", re.IGNORECASE)

PLACEHOLDER_VALUES = {
    "",
    "none",
    "null",
    "changeme",
    "change-me",
    "your-key",
    "your-api-key",
    "your_api_key",
    "yoursecret",
    "sk-xxx",
    "sk-xxxx",
    "sk-placeholder",
    "example-key",
    "put-your-key-here",
}

ENV_VAR_VALUE_RE = re.compile(r"^\$\{?[A-Za-z_][A-Za-z0-9_]*\}?$")

HOME_PATH_RE = re.compile(
    r"(?P<path>(/home/[^/\s\"']+(?=/|\b))"
    r"|(/Users/[^/\s\"']+(?=/|\b))"
    r"|([A-Za-z]:[\\/]Users[\\/][^\\/]+))"
)

# Private-ish hostnames commonly used by local model servers
LOCAL_HOSTS = {"localhost", "127.0.0.1", "0.0.0.0", "::1"}

URL_RE = re.compile(r"^(?P<scheme>[a-zA-Z][a-zA-Z0-9+.-]*)://(?P<rest>.+)$")


# ---------------------------------------------------------------------------
# Issue model
# ---------------------------------------------------------------------------


@dataclass
class Issue:
    severity: str  # "error", "warn", "info"
    check: str
    message: str
    fix: str = ""
    where: str = ""

    def format(self) -> str:
        icon = {"error": "[error]", "warn": "[warn] ", "info": "[info] "}[self.severity]
        line = f"{icon} {self.check}: {self.message}"
        if self.where:
            line += f" (in {self.where})"
        if self.fix:
            line += "\n    fix-me:\n" + "\n".join(
                "      " + l for l in self.fix.strip("\n").splitlines()
            )
        return line


def get_first(d, *names):
    """Return (key, value) for the first matching key present at any depth
    (deterministic: shallowest then alphabetical key order)."""
    best = None
    for key in sorted(d.keys()):
        v = d[key]
        if key in names and best is None:
            best = (key, v)
        if isinstance(v, dict):
            sub = get_first(v, *names)
            if sub is not None and best is None:
                best = (f"{key}.{sub[0]}", sub[1])
    return best


def iter_keys(d, prefix=""):
    """Yield (dotted_key, value) for every scalar leaf, shallowest first."""
    for key in sorted(d.keys()):
        path = f"{prefix}{key}"
        v = d[key]
        if isinstance(v, dict):
            yield from iter_keys(v, f"{path}.")
        else:
            yield path, v


# ---------------------------------------------------------------------------
# Setting checks
# ---------------------------------------------------------------------------


URLISH_KEYS = ("base_url", "baseurl", "endpoint", "url", "api_base")


def check_base_url(cfg, include_missing=True):
    """Validate every URL-like setting, plus flags when there's none at all."""
    issues = []
    url_hits = []
    for path_key, value in iter_keys(cfg):
        leaf = path_key.split(".")[-1]
        if leaf in URLISH_KEYS:
            url_hits.append((path_key, value))

    if not url_hits:
        if include_missing:
            issues.append(
                Issue(
                    "warn",
                    "base-url",
                    "no base_url found; nothing to validate",
                    "base_url: http://localhost:11434/v1\nmodel: llama3",
                    "top level",
                )
            )
        return issues

    for key_path, value in url_hits:
        issues.extend(_check_one_url(key_path, value))
    return issues


def _check_one_url(key_path, value):
    issues = []
    if value is None or (isinstance(value, str) and not value.strip()):
        issues.append(
            Issue(
                "error",
                "base-url",
                f"base_url is {value!r}, expected a URL string",
                f"{key_path}: http://localhost:11434/v1",
                key_path,
            )
        )
        return issues

    if not isinstance(value, str):
        issues.append(
            Issue(
                "error",
                "base-url",
                f"base_url should be a URL string, got {type(value).__name__} {value!r}",
                f"{key_path}: http://localhost:11434/v1",
                key_path,
            )
        )
        return issues

    url = value.strip()
    if url != value:
        issues.append(
            Issue(
                "warn",
                "base-url",
                "base_url has leading/trailing whitespace",
                f'{key_path}: "{url}"',
                key_path,
            )
        )

    m = URL_RE.match(url)
    if not m:
        issues.append(
            Issue(
                "error",
                "base-url",
                f"base_url {url!r} is missing a scheme like http:// or https://",
                f'{key_path}: "http://{url.strip("/")}"',
                key_path,
            )
        )
        return issues

    scheme, rest = m.group("scheme").lower(), m.group("rest")
    if scheme not in ("http", "https"):
        issues.append(
            Issue(
                "error",
                "base-url",
                f"base_url scheme is {scheme!r}; use http (local) or https (remote)",
                f"{key_path}: http://{rest}",
                key_path,
            )
        )

    for pat, label in SECRET_PATTERNS:
        if pat.search(url):
            issues.append(
                Issue(
                    "error",
                    "base-url",
                    f"base_url contains a pasted {label}; endpoints must not "
                    "hold secrets",
                    f'{key_path}: "http://localhost:11434/v1"',
                    key_path,
                )
            )

    host_port = rest.split("/", 1)[0]
    is_local = any(h in host_port.lower() for h in LOCAL_HOSTS)

    if is_local and scheme == "https":
        issues.append(
            Issue(
                "warn",
                "base-url",
                f"local host {host_port!r} usually serves plain http, not https",
                f'{key_path}: "http://{host_port}/v1"',
                key_path,
            )
        )

    path_part = rest.split("/", 1)[1] if "/" in rest else ""
    has_port = ":" in host_port and not host_port.endswith("]")
    if is_local and not has_port:
        issues.append(
            Issue(
                "info",
                "base-url",
                f"local base_url has no port (default 11434 for Ollama); "
                f"did you mean http://{host_port.split('/')[0]}:11434/v1 ?",
                "",
                key_path,
            )
        )

    uses_ollama = "ollama" in url.lower() or "11434" in host_port.lower()
    if uses_ollama and not path_part.startswith("v1"):
        issues.append(
            Issue(
                "info",
                "base-url",
                "for OpenAI-compatible clients, Ollama's base URL ends in /v1 "
                "(e.g. http://localhost:11434/v1); the /api routes are Ollama-native",
                "",
                key_path,
            )
        )

    return issues


def check_model(cfg):
    issues = []
    found = get_first(cfg, "model", "model_name", "llm")
    if found is None:
        issues.append(
            Issue(
                "warn",
                "model",
                "no model name found",
                "model: llama3",
                "top level",
            )
        )
        return issues
    path_key, value = found

    if value is None or (isinstance(value, str) and not value.strip()):
        issues.append(
            Issue(
                "error",
                "model",
                "model is empty; every client needs an explicit model name",
                "model: llama3",
                path_key,
            )
        )
        return issues

    if not isinstance(value, str):
        issues.append(
            Issue(
                "error",
                "model",
                f"model should be a string, got {type(value).__name__} {value!r}",
                "model: llama3",
                path_key,
            )
        )
        return issues

    model = value.strip()
    if model != value:
        issues.append(
            Issue(
                "warn",
                "model",
                "model name has stray whitespace",
                f'model: "{model}"',
                path_key,
            )
        )
    if " " in model or "\t" in model:
        issues.append(
            Issue(
                "error",
                "model",
                f"model name contains spaces: {model!r}",
                f'model: "{model.replace(chr(32), "-").replace(chr(9), "-")}"',
                path_key,
            )
        )
    if model.lower().startswith(("http://", "https://")):
        issues.append(
            Issue(
                "error",
                "model",
                "model looks like a URL; a URL belongs in base_url",
                "model: llama3",
                path_key,
            )
        )
    if not re.match(r"^[a-zA-Z0-9_.:/~-]+$", model):
        issues.append(
            Issue(
                "error",
                "model",
                f"model name has unusual characters: {model!r}; "
                "local model ids are plain ids like llama3 or mistral:7b",
                "model: llama3",
                path_key,
            )
        )
    if model.lower() != model and "/" not in model and ":" not in model:
        issues.append(
            Issue(
                "info",
                "model",
                "local model ids are usually lowercase (llama3, mistral:7b); "
                "double-check the exact id the server reports",
                "",
                path_key,
            )
        )
    return issues

def check_temperature(cfg):
    issues = []
    found = get_first(cfg, "temperature", "temp")
    if found is None:
        return issues
    path_key, value = found
    if isinstance(value, bool):
        issues.append(
            Issue(
                "error",
                "temperature",
                f"temperature is a boolean ({value!r}); it must be a number",
                "temperature: 0.7",
                path_key,
            )
        )
        return issues
    if isinstance(value, str):
        try:
            value = float(value)
        except ValueError:
            issues.append(
                Issue(
                    "error",
                    "temperature",
                    f"temperature is a non-numeric string {value!r}",
                    "temperature: 0.7",
                    path_key,
                )
            )
            return issues
    if not isinstance(value, (int, float)):
        issues.append(
            Issue(
                "error",
                "temperature",
                f"temperature is {type(value).__name__}; it must be a number",
                "temperature: 0.7",
                path_key,
            )
        )
        return issues
    if not 0.0 <= float(value) <= 2.0:
        issues.append(
            Issue(
                "error",
                "temperature",
                f"temperature {value} is outside the supported range 0.0-2.0",
                (
                    "temperature: 0.0" if float(value) < 0 else "temperature: 2.0"
                ),
                path_key,
            )
        )
    elif float(value) > 1.0:
        issues.append(
            Issue(
                "info",
                "temperature",
                f"temperature {value} is above 1.0; many local models get "
                "incoherent there - try 0.1-1.0 for tool use",
                "",
                path_key,
            )
        )
    return issues


_TIMEOUT_MAX_DEFAULT = 600


def check_timeout(cfg):
    issues = []
    found = get_first(
        cfg, "timeout", "timeout_seconds", "request_timeout", "read_timeout", "time_out"
    )
    if found is None:
        return issues
    path_key, value = found
    if isinstance(value, str):
        stripped = value.strip()
        if stripped.isdigit():
            issues.append(
                Issue(
                    "warn",
                    "timeout",
                    f"timeout is quoted: {value!r}; use a bare number",
                    f"{path_key}: {int(stripped)}",
                    path_key,
                )
            )
            value = int(stripped)
        else:
            m = re.match(
                r"^(\d+)\s*(ms|s|sec|secs|seconds|m|min|minutes)?$",
                stripped,
                re.IGNORECASE,
            )
            if not m:
                issues.append(
                    Issue(
                        "error",
                        "timeout",
                        f"timeout {value!r} is not a number of seconds",
                        f"{path_key}: 60",
                        path_key,
                    )
                )
                return issues
            num = int(m.group(1))
            unit = (m.group(2) or "s").lower()
            if unit == "ms":
                if num < 1000:
                    issues.append(
                        Issue(
                            "warn",
                            "timeout",
                            f"timeout {value} looks like milliseconds; most "
                            "OpenAI-compatible clients take seconds",
                            f"{path_key}: {max(num // 1000, 1)}",
                            path_key,
                        )
                    )
                    return issues
                issues.append(
                    Issue(
                        "warn",
                        "timeout",
                        f"timeout written in milliseconds ({num}ms); "
                        "prefer a plain number of seconds",
                        f"{path_key}: {num // 1000}",
                        path_key,
                    )
                )
                value = num / 1000.0
                if value < 1 or value > _TIMEOUT_MAX_DEFAULT:
                    return issues
            elif unit in ("m", "min", "minutes"):
                value = num * 60
                issues.append(
                    Issue(
                        "info",
                        "timeout",
                        f"timeout written as minutes ({value}s total); "
                        "prefer a plain number of seconds",
                        f"{path_key}: {value}",
                        path_key,
                    )
                )
            else:
                value = num
    if isinstance(value, bool):
        issues.append(
            Issue(
                "error",
                "timeout",
                "timeout is a boolean; it must be a number of seconds",
                "timeout: 60",
                path_key,
            )
        )
        return issues
    if not isinstance(value, (int, float)):
        issues.append(
            Issue(
                "error",
                "timeout",
                f"timeout is {type(value).__name__}; it must be a number of seconds",
                "timeout: 60",
                path_key,
            )
        )
        return issues

    if value < 1:
        issues.append(
            Issue(
                "error",
                "timeout",
                f"timeout {value}s is under 1s; local model servers take a while "
                "to load models and will fail constantly",
                "timeout: 60",
                path_key,
            )
        )
    elif value > _TIMEOUT_MAX_DEFAULT:
        issues.append(
            Issue(
                "warn",
                "timeout",
                f"timeout {int(value)}s is over {_TIMEOUT_MAX_DEFAULT}s; that hides "
                "hung servers - cap it and fail visibly",
                f"timeout: {_TIMEOUT_MAX_DEFAULT}",
                path_key,
            )
        )
    return issues


def _article(phrase):
    return "an" if phrase[0].lower() in "aeiou" else "a"


def check_api_key(cfg):
    """Flag accidentally pasted API keys anywhere in the config."""
    issues = []
    for path_key, value in iter_keys(cfg):
        if not isinstance(value, str):
            continue
        if ENV_VAR_VALUE_RE.match(value):
            continue  # correctly referenced from the environment
        real = [label for pat, label in SECRET_PATTERNS if pat.search(value)]
        if real:
            article = _article(real[0])
            if HOST_KEY_RE.search(path_key.split(".")[-1]):
                issues.append(
                    Issue(
                        "error",
                        "pasted-secret",
                        f"{path_key} holds {article} {real[0]}. Secrets in "
                        "config files get committed and copied - reference "
                        "an environment variable instead",
                        f"{path_key}: ${{MY_API_KEY}}",
                        path_key,
                    )
                )
            else:
                issues.append(
                    Issue(
                        "error",
                        "pasted-secret",
                        f"{path_key} holds {article} {real[0]} in a non-key "
                        "field - almost certainly pasted by accident; keys "
                        "belong in environment variables",
                        f"# {path_key} should hold a proper value, not a key",
                        path_key,
                    )
                )
        elif (
            HOST_KEY_RE.search(path_key.split(".")[-1])
            and value.lower() not in PLACEHOLDER_VALUES
            and value.strip()
        ):
            issues.append(
                Issue(
                    "warn",
                    "pasted-secret",
                    f"{path_key} holds a hard-coded value ({_redact(value)}); "
                    "move it to an environment variable",
                    f"{path_key}: ${{MY_API_KEY}}",
                    path_key,
                )
            )
    return issues


def check_home_paths(cfg):
    """Personal home directories (/home/alice, /Users/alice-bob) don't travel."""
    issues = []
    for path_key, value in iter_keys(cfg):
        if not isinstance(value, str):
            continue
        for m in HOME_PATH_RE.finditer(value):
            issues.append(
                Issue(
                    "warn",
                    "personal-path",
                    f"{path_key} uses a personal home path "
                    f"({m.group('path')}); configs referencing your home "
                    "directory break on other machines and leak your username",
                    f"{path_key}: relative-or-XDG-path",
                    path_key,
                )
            )
    return issues


def check_unknown_keys(cfg):
    known = {
        "base_url", "baseurl", "endpoint", "url", "api_base", "model",
        "model_name", "llm", "temperature", "temp", "timeout",
        "timeout_seconds", "request_timeout", "read_timeout", "time_out",
        "api_key", "apikey", "auth", "token", "secret", "password",
        "max_tokens", "top_p", "provider", "client", "options", "name",
        "provider_name", "description",
    }
    issues = []
    for path_key, _ in iter_keys(cfg):
        leaf = path_key.split(".")[-1]
        if leaf not in known:
            issues.append(
                Issue(
                    "info",
                    "unknown-setting",
                    f"{path_key} is not a setting this linter knows; "
                    "typo'd settings are silently ignored by most tools",
                    "",
                    path_key,
                )
            )
    return issues


def _redact(value: str) -> str:
    if len(value) <= 6:
        return "***"
    return value[:4] + "..." + value[-2:]


# ---------------------------------------------------------------------------
# File hygiene
# ---------------------------------------------------------------------------


def check_file_permissions(path):
    """Config files should not be world-readable or world-writable
    (group/other permissions at all are suspicious for secret-adjacent files)."""
    issues = []
    try:
        mode = stat.S_IMODE(os.stat(path).st_mode)
    except OSError as e:
        return [
            Issue("error", "file-permissions", f"cannot stat {path}: {e}", "", str(path))
        ]
    world_read = mode & stat.S_IROTH
    world_write = mode & stat.S_IWOTH
    group_read = mode & stat.S_IRGRP
    how = f"chmod o-rwx {path}" if world_read or world_write else f"chmod g-rwx {path}"
    if world_write:
        issues.append(
            Issue(
                "error",
                "file-permissions",
                f"{path} is world-WRITABLE (mode {format(mode, '04o')}); "
                "anyone on the machine can edit your settings",
                how,
                str(path),
            )
        )
    elif group_read or world_read:
        who = "world" if world_read else "group"
        issues.append(
            Issue(
                "warn",
                "file-permissions",
                f"{path} is {who}-readable (mode {format(mode, '04o')}); "
                "tighten it so only you (and your group, if intended) can read it",
                how,
                str(path),
            )
        )
    return issues


def check_file_secret_free(path):
    """Raw content scan of the file itself for anything key-shaped."""
    issues = []
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            lines = f.readlines()
    except OSError:
        return issues
    for i, line in enumerate(lines, start=1):
        # skip env-var references and obvious placeholders
        stripped = line.strip()
        if stripped.startswith("#") or "$" in stripped:
            continue
        if "xxx" in stripped.lower() or "placeholder" in stripped.lower():
            continue
        # Only flag values, not schema-looking keys (e.g. `api_key: ${VAR}`)
        _, _, after_colon = stripped.partition(":")
        probe = after_colon or stripped
        for pat, label in SECRET_PATTERNS:
            m = pat.search(probe)
            if m:
                issues.append(
                    Issue(
                        "error",
                        "file-secret",
                        f"{path}:{i} contains {_article(label)} {label} "
                        f"({_redact(m.group(0))}) as raw text",
                        "# move it to the environment and reference $VARS here",
                        f"{path}:{i}",
                    )
                )
    return issues
