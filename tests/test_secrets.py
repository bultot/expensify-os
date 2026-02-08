"""Tests for 1Password secret resolution."""

from __future__ import annotations

import subprocess
from unittest.mock import patch

import pytest

from expensify_os.utils.secrets import (
    is_secret_reference,
    resolve_secret,
    resolve_secrets_in_dict,
)


class TestIsSecretReference:
    def test_valid_reference(self):
        assert is_secret_reference("op://vault/item/field") is True

    def test_plain_string(self):
        assert is_secret_reference("just-a-string") is False

    def test_empty_string(self):
        assert is_secret_reference("") is False


class TestResolveSecret:
    def test_plain_string_passthrough(self):
        assert resolve_secret("plain-value") == "plain-value"

    @patch("subprocess.run")
    def test_resolves_op_reference(self, mock_run):
        mock_run.return_value = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="resolved-secret\n", stderr=""
        )
        result = resolve_secret("op://vault/item/field")
        assert result == "resolved-secret"
        mock_run.assert_called_once()

    @patch("subprocess.run", side_effect=FileNotFoundError)
    def test_op_not_installed(self, _mock_run):
        with pytest.raises(RuntimeError, match="not installed"):
            resolve_secret("op://vault/item/field")

    @patch("subprocess.run")
    def test_op_failure(self, mock_run):
        mock_run.side_effect = subprocess.CalledProcessError(
            1, "op", stderr="item not found"
        )
        with pytest.raises(RuntimeError, match="Failed to resolve"):
            resolve_secret("op://vault/item/field")


class TestResolveSecretsInDict:
    @patch("expensify_os.utils.secrets.resolve_secret")
    def test_resolves_nested_refs(self, mock_resolve):
        mock_resolve.side_effect = lambda ref: f"resolved:{ref}"

        data = {
            "plain": "value",
            "secret": "op://vault/item/field",
            "nested": {
                "deep_secret": "op://vault/item/deep",
                "plain_nested": "ok",
            },
        }
        result = resolve_secrets_in_dict(data)

        assert result["plain"] == "value"
        assert result["secret"] == "resolved:op://vault/item/field"
        assert result["nested"]["deep_secret"] == "resolved:op://vault/item/deep"
        assert result["nested"]["plain_nested"] == "ok"
