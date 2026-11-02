"""Tests for the setting checks (base_url, model, temperature, timeout)."""
from llm_config_linter.linter import (
    check_base_url,
    check_home_paths,
    check_model,
    check_temperature,
    check_timeout,
)
from llm_config_linter.loader import load_config
from tests.conftest import fixture, private_copy


# --- base_url ---------------------------------------------------------

def test_good_local_url():
    assert not check_base_url({"base_url": "http://localhost:11434/v1"})


def test_good_remote_url():
    assert not check_base_url({"base_url": "https://api.openai.com/v1"})


def test_missing_scheme():
    issues = check_base_url({"base_url": "localhost:11434/v1"})
    assert any(i.severity == "error" and "missing" in i.message for i in issues)


def test_bad_scheme():
    issues = check_base_url({"base_url": "ftp://example.com/v1"})
    assert any(i.severity == "error" for i in issues)


def test_local_https_flagged():
    issues = check_base_url({"base_url": "https://localhost:11434/v1"})
    assert any(i.severity == "warn" for i in issues)


def test_local_url_without_port():
    issues = check_base_url({"base_url": "http://localhost/v1"})
    assert any(i.severity == "info" and "port" in i.message for i in issues)


def test_ollama_without_v1_hint():
    issues = check_base_url({"base_url": "http://localhost:11434/api"})
    assert any("Ollama" in i.message for i in issues)


def test_no_base_url_at_all():
    issues = check_base_url({"model": "llama3"})
    assert any(i.severity == "warn" and "no base_url" in i.message for i in issues)


def test_empty_base_url():
    issues = check_base_url({"base_url": ""})
    assert any(i.severity == "error" for i in issues)


def test_url_with_past_key():
    issues = check_base_url(
        {"base_url": "https://api.openai.com/v1?api_key=sk-abcdefghijklmnopqrtuvwx"}
    )
    assert any(i.severity == "error" for i in issues)


def test_nested_base_url_found():
    issues = check_base_url({"provider": {"base_url": "http://localhost:11434/v1"}})
    assert not issues


# --- model ------------------------------------------------------------

def test_good_model():
    assert not check_model({"model": "llama3"})


def test_good_tagged_model():
    assert not check_model({"model": "mistral:7b"})


def test_empty_model():
    issues = check_model({"model": ""})
    assert any(i.severity == "error" for i in issues)


def test_model_with_spaces_flags():
    issues = check_model({"model": "llama 3"})
    assert any(i.severity == "error" and "spaces" in i.message for i in issues)


def test_model_is_url():
    issues = check_model({"model": "http://localhost:11434"})
    assert any(i.severity == "error" for i in issues)


def test_missing_model():
    issues = check_model({"base_url": "http://localhost:11434/v1"})
    assert any(i.severity == "warn" for i in issues)


def test_model_case_info():
    issues = check_model({"model": "Llama3"})
    assert all(i.severity == "info" for i in issues)


# --- temperature ------------------------------------------------------

def test_good_temperature():
    assert not check_temperature({"temperature": 0.7})


def test_zero_and_two_ok():
    for issues in (
        check_temperature({"temperature": 0}),
        check_temperature({"temperature": 2.0}),
    ):
        assert not [i for i in issues if i.severity in ("error", "warn")]


def test_out_of_range_temperature():
    issues = check_temperature({"temperature": 3.5})
    assert any(i.severity == "error" and "0.0-2.0" in i.message for i in issues)


def test_negative_temperature():
    issues = check_temperature({"temperature": -0.1})
    assert any(i.severity == "error" for i in issues)


def test_string_temperature_coerced():
    assert not check_temperature({"temperature": "0.7"})


def test_bad_string_temperature():
    issues = check_temperature({"temperature": "hot"})
    assert any(i.severity == "error" for i in issues)


def test_high_temperature_info():
    issues = check_temperature({"temperature": 1.5})
    assert any(i.severity == "info" for i in issues)


# --- timeout ----------------------------------------------------------

def test_good_timeout():
    assert not check_timeout({"timeout": 60})


def test_quoted_timeout():
    issues = check_timeout({"timeout": "120"})
    assert any(i.severity == "warn" for i in issues)


def test_timeout_with_unit_seconds():
    issues = check_timeout({"timeout": "30s"})
    assert not [i for i in issues if i.severity == "error"]


def test_timeout_ms_flagged():
    issues = check_timeout({"timeout": "30000ms"})
    assert any("milliseconds" in i.message for i in issues)


def test_timeout_sub_second_flagged():
    issues = check_timeout({"timeout": 0.5})
    assert any(i.severity == "error" and "under 1s" in i.message for i in issues)


def test_timeout_too_big():
    issues = check_timeout({"timeout": 3600})
    assert any(i.severity == "warn" for i in issues)


def test_timeout_too_small():
    issues = check_timeout({"timeout": 0})
    assert any(i.severity == "error" for i in issues)


def test_timeout_minutes_info():
    issues = check_timeout({"timeout": "2 min"})
    assert any(i.severity == "info" for i in issues)


def test_nonsense_timeout():
    issues = check_timeout({"timeout": "banana"})
    assert any(i.severity == "error" for i in issues)


def test_missing_timeout_ok():
    assert not check_timeout({})


# --- home paths -------------------------------------------------------

def test_linux_home_path():
    issues = check_home_paths({"cache_dir": "/home/dylan/.cache/ollama"})
    assert any(i.check == "personal-path" for i in issues)


def test_mac_home_path():
    issues = check_home_paths({"models_dir": "/Users/Dylan/models"})
    assert any(i.check == "personal-path" for i in issues)


def test_windows_home_path():
    issues = check_home_paths({"_dir": 'C:\\Users\\dylan\\models'})
    assert any(i.check == "personal-path" for i in issues)


def test_relative_path_ok():
    assert not check_home_paths({"cache_dir": "~/.cache/ollama"})
    assert not check_home_paths({"cache_dir": "/var/lib/ollama"})


# --- integration of check helpers with parsed configs -----------------

def test_checks_run_on_yaml_fixture():
    cfg, _ = load_config(fixture("pasted-key.yaml"))
    url_issues = check_base_url(cfg)
    assert not [i for i in url_issues if i.severity == "error"]


def test_clean_fixtures_as_private_files(tmp_path):
    cfg, kind = load_config(private_copy(tmp_path, "good.yaml"))
    assert kind == "yaml"
