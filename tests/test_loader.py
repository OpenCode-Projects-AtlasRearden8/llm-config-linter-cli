"""Tests for the config loader (YAML + TOML, normalization, errors)."""
import pytest

from llm_config_linter.loader import ConfigParseError, load_config


def test_load_yaml_good(tmp_path):
    p = tmp_path / "good.yaml"
    p.write_text("base_url: http://localhost:11434/v1\nmodel: llama3\n")
    data, kind = load_config(p)
    assert kind == "yaml"
    assert data["base_url"] == "http://localhost:11434/v1"
    assert data["model"] == "llama3"


def test_load_toml(tmp_path):
    p = tmp_path / "good.toml"
    p.write_text(
        'base_url = "http://127.0.0.1:11434/v1"\n'
        'model = "mistral:7b"\ntimeout = 120\n'
    )
    data, kind = load_config(p)
    assert kind == "toml"
    assert data["timeout"] == 120


def test_key_normalization(tmp_path):
    p = tmp_path / "weird.yaml"
    p.write_text("Base-URL: http://x\nAPI.KEY: y\n")
    data, _ = load_config(p)
    assert data == {"base_url": "http://x", "api_key": "y"}


def test_broken_yaml_raises(tmp_path):
    p = tmp_path / "broken.yaml"
    p.write_text("model: [unclosed\n  temperature: 0.7\n")
    with pytest.raises(ConfigParseError):
        load_config(p)


def test_bad_extension_raises(tmp_path):
    p = tmp_path / "config.ini"
    p.write_text("model=llama3\n")
    with pytest.raises(ConfigParseError):
        load_config(p)


def test_top_level_scalar_raises(tmp_path):
    p = tmp_path / "scalar.yaml"
    p.write_text("just a string\n")
    with pytest.raises(ConfigParseError):
        load_config(p)


def test_missing_file_raises(tmp_path):
    with pytest.raises(ConfigParseError):
        load_config(tmp_path / "nope.yaml")


def test_yaml_and_toml_equivalent(tmp_path):
    py = tmp_path / "a.yaml"
    pt = tmp_path / "b.toml"
    py.write_text("base_url: 'http://h:1/v1'\nmodel: llama3\ntimeout: 60\n")
    pt.write_text('base_url = "http://h:1/v1"\nmodel = "llama3"\ntimeout = 60\n')
    dy, _ = load_config(py)
    dt, _ = load_config(pt)
    assert dy == dt
