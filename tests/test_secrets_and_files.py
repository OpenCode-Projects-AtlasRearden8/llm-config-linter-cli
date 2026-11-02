"""Tests for secret detection and file hygiene checks."""
import os
import stat

from llm_config_linter.linter import (
    check_api_key,
    check_file_permissions,
    check_file_secret_free,
)
from tests.conftest import fixture


# --- pasted secrets in values -----------------------------------------

def test_openai_key_shape_detected():
    cfg = {
        "api_key": "sk-sample-test-key-not-real-1234567890abcdef",
    }
    issues = check_api_key(cfg)
    assert any(i.severity == "error" and "OpenAI" in i.message for i in issues)


def test_various_key_shapes_detected():
    for value in [
        "sk-sample-test-key-not-real-1234567890abcdef",
        "gsk_" + "a" * 24,
        "hf_" + "b" * 24,
        "ghp_" + "c" * 36,
        "AKIA" + "1234ABCD9012EFGH".replace("", "")[:16],
    ]:
        issues = check_api_key({"api_key": value})
        assert issues, f"{value[:6]}... should be flagged"


def test_env_var_reference_ok():
    cfg = {"api_key": "${MY_API_KEY}"}
    assert not check_api_key(cfg)


def test_empty_key_ok():
    assert not check_api_key({"api_key": ""})
    assert not check_api_key({"api_key": "sk-xxx"})


def test_key_in_non_key_field():
    cfg = {"description": "my key is sk-sample-test-key-not-real-1234567890abcdef"}
    issues = check_api_key(cfg)
    assert any("non-key field" in i.message for i in issues)


def test_placeholder_key_ok():
    assert not check_api_key({"api_key": "your-key"})
    assert not check_api_key({"api_key": "PUT-YOUR-KEY-HERE"})


def test_hardcoded_nonstandard_key_warns():
    cfg = {"api_key": "abcd1234efgh5678ijkl"}
    issues = check_api_key(cfg)
    assert any(i.severity == "warn" for i in issues)


def test_clean_config_no_secret_issues():
    cfg = {
        "base_url": "http://localhost:11434/v1",
        "model": "llama3",
        "api_key": "",
        "timeout": 60,
        "temperature": 0.7,
    }
    assert not check_api_key(cfg)


# --- file content scanning --------------------------------------------

def test_fixture_file_has_secret_flagged():
    issues = check_file_secret_free(fixture("pasted-key.yaml"))
    assert any(i.check == "file-secret" for i in issues)


def test_good_file_is_secret_free():
    assert not check_file_secret_free(fixture("good.yaml"))
    assert not check_file_secret_free(fixture("good.toml"))


# --- permissions ------------------------------------------------------

def test_private_file_ok(tmp_path):
    p = tmp_path / "c.yaml"
    p.write_text("model: llama3\n")
    os.chmod(p, stat.S_IRUSR | stat.S_IWUSR)  # 600
    assert not check_file_permissions(p)


def test_world_readable_flagged(tmp_path):
    p = tmp_path / "c.yaml"
    p.write_text("model: llama3\n")
    os.chmod(p, stat.S_IRUSR | stat.S_IWUSR | stat.S_IROTH | stat.S_IRGRP)  # 644
    issues = check_file_permissions(p)
    assert issues and all(i.severity == "warn" for i in issues)


def test_world_writable_error(tmp_path):
    p = tmp_path / "c.yaml"
    p.write_text("model: llama3\n")
    os.chmod(p, stat.S_IRUSR | stat.S_IWUSR | stat.S_IWOTH)  # 602
    issues = check_file_permissions(p)
    assert any(i.severity == "error" and "world-WRITABLE" in i.message for i in issues)
