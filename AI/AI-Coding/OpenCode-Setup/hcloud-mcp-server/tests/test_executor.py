import pytest
from unittest.mock import patch, MagicMock

from src.executor import execute_command, _build_full_command, _is_obs_command
from src.config import ExecutionConfig


class TestIsObsCommand:
    def test_obs_command(self):
        assert _is_obs_command(["obs", "ls"]) is True

    def test_obs_uppercase(self):
        assert _is_obs_command(["OBS", "ls"]) is True

    def test_non_obs_command(self):
        assert _is_obs_command(["IAM", "ListCustomPolicies"]) is False

    def test_obs_with_flags_before(self):
        assert _is_obs_command(["--cli-region=la-north-2", "obs", "ls"]) is True

    def test_empty_args(self):
        assert _is_obs_command([]) is False


class TestBuildFullCommand:
    def test_help_command(self):
        config = ExecutionConfig()
        cmd = _build_full_command("--help", config)
        assert cmd[0] == "hcloud"
        assert "--help" in cmd
        assert "--cli-output=json" in cmd

    def test_service_help(self):
        config = ExecutionConfig()
        cmd = _build_full_command("IAM --help", config)
        assert cmd == ["hcloud", "IAM", "--help", "--cli-output=json"]

    def test_operation_with_params(self):
        config = ExecutionConfig()
        cmd = _build_full_command("IAM ListCustomPolicies --page=1", config)
        assert "IAM" in cmd
        assert "ListCustomPolicies" in cmd
        assert "--page=1" in cmd

    def test_no_duplicate_cli_output(self):
        config = ExecutionConfig()
        cmd = _build_full_command("IAM ListCustomPolicies --cli-output=table", config)
        cli_output_args = [a for a in cmd if a.startswith("--cli-output")]
        assert len(cli_output_args) == 1
        assert cli_output_args[0] == "--cli-output=table"

    def test_custom_binary(self):
        config = ExecutionConfig(hcloud_binary="/usr/local/bin/hcloud")
        cmd = _build_full_command("--help", config)
        assert cmd[0] == "/usr/local/bin/hcloud"


class TestBuildFullCommandOBS:
    def test_obs_no_cli_output(self):
        config = ExecutionConfig()
        cmd = _build_full_command("obs ls", config)
        assert cmd == ["hcloud", "obs", "ls"]
        assert not any(a.startswith("--cli-output") for a in cmd)

    def test_obs_help_no_cli_output(self):
        config = ExecutionConfig()
        cmd = _build_full_command("obs help ls", config)
        assert cmd == ["hcloud", "obs", "help", "ls"]

    def test_obs_cli_region_translated(self):
        config = ExecutionConfig()
        cmd = _build_full_command("obs ls --cli-region=la-north-2", config)
        assert "--cli-region=la-north-2" not in cmd
        assert "-e=https://obs.la-north-2.myhuaweicloud.com" in cmd
        assert "obs" in cmd
        assert "ls" in cmd

    def test_obs_cli_region_custom_template(self):
        config = ExecutionConfig(obs_endpoint_template="https://obs.{region}.myhuaweicloud.com.cn")
        cmd = _build_full_command("obs ls --cli-region=cn-north-4", config)
        assert "-e=https://obs.cn-north-4.myhuaweicloud.com.cn" in cmd

    def test_obs_no_region_no_endpoint(self):
        config = ExecutionConfig()
        cmd = _build_full_command("obs ls", config)
        assert not any(a.startswith("-e=") for a in cmd)

    def test_obs_uppercase(self):
        config = ExecutionConfig()
        cmd = _build_full_command("OBS ls", config)
        assert not any(a.startswith("--cli-output") for a in cmd)

    def test_obs_rm_with_region(self):
        config = ExecutionConfig()
        cmd = _build_full_command("obs rm obs://bucket/key --cli-region=la-north-2", config)
        assert "-e=https://obs.la-north-2.myhuaweicloud.com" in cmd
        assert "--cli-region=la-north-2" not in cmd


class TestExecuteCommand:
    @patch("src.executor.subprocess.run")
    def test_successful_execution(self, mock_run):
        mock_run.return_value = MagicMock(
            stdout='{"total_number": 2}',
            stderr="",
            returncode=0,
        )
        config = ExecutionConfig()
        stdout, stderr, rc = execute_command("IAM ListCustomPolicies", config)
        assert rc == 0
        assert "total_number" in stdout

    @patch("src.executor.subprocess.run")
    def test_timeout(self, mock_run):
        import subprocess
        mock_run.side_effect = subprocess.TimeoutExpired(cmd="hcloud", timeout=30)
        config = ExecutionConfig()
        stdout, stderr, rc = execute_command("IAM ListCustomPolicies", config)
        assert rc == -1
        assert "timed out" in stderr

    @patch("src.executor.subprocess.run")
    def test_obs_execution_no_cli_output(self, mock_run):
        mock_run.return_value = MagicMock(
            stdout="Bucket number: 1",
            stderr="",
            returncode=0,
        )
        config = ExecutionConfig()
        stdout, stderr, rc = execute_command("obs ls", config)
        called_cmd = mock_run.call_args[0][0]
        assert not any(a.startswith("--cli-output") for a in called_cmd)
