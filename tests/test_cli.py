"""End-to-end tests running the CLI against fixture files."""
import json
import subprocess
import sys

from llm_config_linter import cli
from tests.conftest import fixture, private_copy


def run_cli(*args):
    return subprocess.run(
        [sys.executable, "-m", "llm_config_linter.cli", *args],
        capture_output=True,
        text=True,
    )


def test_good_yaml_is_clean(tmp_path):
    issues, cfg, kind = cli.lint_file(private_copy(tmp_path, "good.yaml"))
    assert not [i for i in issues if i.severity in ("error", "warn")]


def test_good_toml_is_clean(tmp_path):
    issues, cfg, kind = cli.lint_file(private_copy(tmp_path, "good.toml"))
    assert not [i for i in issues if i.severity in ("error", "warn")]


def test_pasted_key_fixture_finds_errors():
    issues, _, _ = cli.lint_file(fixture("pasted-key.yaml"))
    checks = {i.check for i in issues}
    assert "pasted-secret" in checks
    assert "file-secret" in checks
    assert "personal-path" in checks
    assert "temperature" in checks


def test_minimal_fixture_flags_missing():
    issues, _, _ = cli.lint_file(fixture("minimal.yaml"))
    messages = "\n".join(i.message for i in issues)
    assert "no base_url" in messages
    assert any(i.check == "model" for i in issues)


def test_broken_yaml_reports_parse_error():
    issues, cfg, kind = cli.lint_file(fixture("broken.yaml"))
    assert cfg is None and kind is None
    assert issues and issues[0].check == "parse"


def test_nested_env_reference_is_fine(tmp_path):
    issues, cfg, kind = cli.lint_file(private_copy(tmp_path, "nested-env.yaml"))
    assert not [i for i in issues if i.severity in ("error", "warn")]


def test_cli_exit_code_1_on_errors():
    r = run_cli(fixture("pasted-key.yaml"))
    assert r.returncode == 1


def test_cli_exit_code_0_on_clean(tmp_path):
    r = run_cli(private_copy(tmp_path, "good.yaml"))
    assert r.returncode == 0


def test_cli_missing_file_exit_2():
    r = run_cli("definitely-not-here.yaml")
    assert r.returncode == 2


def test_cli_json_output():
    r = run_cli("--json", fixture("pasted-key.yaml"))
    data = json.loads(r.stdout)
    assert isinstance(data, list)
    assert data[0]["file"].endswith("pasted-key.yaml")
    assert any(i["check"] == "pasted-secret" for i in data[0]["issues"])


def test_cli_all_clear_prints_summary_card(tmp_path):
    r = run_cli(private_copy(tmp_path, "good.toml"))
    assert "config looks healthy" in r.stdout
    assert "config summary" in r.stdout
    assert r.returncode == 0


def test_cli_multiple_files(tmp_path):
    r = run_cli(private_copy(tmp_path, "good.yaml"), private_copy(tmp_path, "pasted-key.yaml"))
    # pasted-key fixture keeps its sample key out of the real world in tests only
    assert "good.yaml" in r.stdout
    assert "pasted-key.yaml" in r.stdout
    assert r.returncode == 1


def test_cli_version_displayed():
    r = run_cli("--version")
    assert r.returncode == 0 and "llm-config-lint" in r.stdout


def test_fixtures_are_not_real_keys():
    """Safety net: fixture content must stay clearly non-secret."""
    name = fixture("pasted-key.yaml")
    content = open(name).read()
    assert "not-real" in content or "sample" in content
