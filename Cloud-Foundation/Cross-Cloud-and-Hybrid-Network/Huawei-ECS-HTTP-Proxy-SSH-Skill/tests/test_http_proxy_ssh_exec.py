import importlib.util
import os
import pathlib
import types
import unittest
from unittest import mock


SCRIPT_PATH = (
    pathlib.Path(__file__).resolve().parents[1] / "scripts" / "http_proxy_ssh_exec.py"
)
SPEC = importlib.util.spec_from_file_location("http_proxy_ssh_exec", SCRIPT_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


class ConnectProxyTests(unittest.TestCase):
    @mock.patch.dict(os.environ, {"HTTPS_PROXY": "https://proxy.example:8443"}, clear=True)
    def test_https_proxy_uses_tls_wrapping(self):
        raw_socket = mock.Mock()
        wrapped_socket = mock.Mock()
        wrapped_socket.recv.side_effect = [b"HTTP/1.1 200 Connection established\r\n\r\n"]

        ssl_context = mock.Mock()
        ssl_context.wrap_socket.return_value = wrapped_socket

        with mock.patch.object(MODULE.socket, "create_connection", return_value=raw_socket):
            with mock.patch.object(MODULE.ssl, "create_default_context", return_value=ssl_context):
                result = MODULE.connect_proxy("ecs.example", 22)

        self.assertIs(result, wrapped_socket)
        ssl_context.wrap_socket.assert_called_once_with(raw_socket, server_hostname="proxy.example")


class MainTests(unittest.TestCase):
    @mock.patch.dict(os.environ, {"HTTP_PROXY": "http://proxy.example:8080"}, clear=True)
    def test_main_does_not_auto_accept_unknown_host_keys(self):
        stdout = types.SimpleNamespace(
            readline=mock.Mock(side_effect=["", ""]),
            channel=types.SimpleNamespace(recv_exit_status=mock.Mock(return_value=0)),
        )
        stderr = types.SimpleNamespace(read=mock.Mock(return_value=b""))
        ssh_client = mock.Mock()
        ssh_client.exec_command.return_value = (None, stdout, stderr)

        paramiko_stub = types.SimpleNamespace(
            SSHClient=mock.Mock(return_value=ssh_client),
            AutoAddPolicy=mock.Mock(name="AutoAddPolicy"),
            RejectPolicy=mock.Mock(name="RejectPolicy"),
            RSAKey=types.SimpleNamespace(from_private_key_file=mock.Mock(return_value=object())),
            ECDSAKey=types.SimpleNamespace(from_private_key_file=mock.Mock(side_effect=ValueError("skip"))),
            Ed25519Key=types.SimpleNamespace(from_private_key_file=mock.Mock(side_effect=ValueError("skip"))),
        )

        argv = [
            "http_proxy_ssh_exec.py",
            "--host",
            "ecs.example",
            "--port",
            "22",
            "--user",
            "root",
            "--key",
            "/tmp/test-key",
            "--command",
            "true",
        ]

        with mock.patch.object(MODULE, "connect_proxy", return_value=mock.Mock()):
            with mock.patch.object(MODULE, "load_key", return_value=object()):
                with mock.patch.dict(MODULE.sys.modules, {"paramiko": paramiko_stub}):
                    with mock.patch.object(MODULE.sys, "argv", argv):
                        rc = MODULE.main()

        self.assertEqual(rc, 0)
        ssh_client.set_missing_host_key_policy.assert_called_once_with(
            paramiko_stub.RejectPolicy.return_value
        )
        paramiko_stub.AutoAddPolicy.assert_not_called()


if __name__ == "__main__":
    unittest.main()
