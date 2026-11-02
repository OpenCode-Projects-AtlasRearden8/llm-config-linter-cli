"""Load YAML/TOML config files into a plain dict."""
import os
import tomllib
from pathlib import Path

import yaml


def normalize_key(key: str) -> str:
    """Lower-case, strip dashes/underscores/periods so 'base-url' == 'base_url'."""
    return key.strip().lower().replace("-", "_").replace(".", "_")


def deep_normalize(obj):
    """Recursively normalize mapping keys."""
    if isinstance(obj, dict):
        return {normalize_key(k): deep_normalize(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [deep_normalize(v) for v in obj]
    return obj


class ConfigParseError(Exception):
    pass


def load_config(path):
    """Load a .yaml/.yml/.toml file, returning (normalized_dict, provider_kind).

    provider_kind is "yaml" or "toml".
    Raises ConfigParseError on unreadable/invalid/unrecognized files.
    """
    name = Path(path).name.lower()
    path_str = os.fspath(path)
    try:
        if name.endswith((".yaml", ".yml")):
            with open(path_str, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)
            kind = "yaml"
        elif name.endswith(".toml"):
            with open(path_str, "rb") as f:
                data = tomllib.load(f)
            kind = "toml"
        else:
            raise ConfigParseError(
                f"unrecognized file type: {path.name} (expected .yaml, .yml, or .toml)"
            )
    except tomllib.TOMLDecodeError as e:
        raise ConfigParseError(f"TOML parse error: {e}") from e
    except yaml.YAMLError as e:
        raise ConfigParseError(f"YAML parse error: {e}") from e
    except OSError as e:
        raise ConfigParseError(f"cannot read file: {e}") from e

    if not isinstance(data, dict):
        raise ConfigParseError(
            "top level of config must be a mapping (key: value pairs)"
        )
    return deep_normalize(data), kind
