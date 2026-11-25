"""Output guard uses real Git markers and preserves immutable task results."""

import importlib.util
from pathlib import Path

import pytest


def exporter():
    path = Path(__file__).resolve().parents[3] / "scripts/verify/export_owner_control.py"
    spec = importlib.util.spec_from_file_location("owner_export_guard", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_empty_dotgit_directory_does_not_make_every_descendant_a_checkout(tmp_path):
    (tmp_path / ".git").mkdir()
    code = tmp_path / "code"
    code.mkdir()
    data = tmp_path / "data"
    data.mkdir()
    output = data / "new"
    assert exporter().fresh_output(output, code, data) == output


def test_real_git_marker_and_existing_output_rejected(tmp_path):
    code = tmp_path / "code"
    code.mkdir()
    data = tmp_path / "data"
    data.mkdir()
    (data / ".git").mkdir()
    (data / ".git/HEAD").write_text("ref: refs/heads/main\n")
    with pytest.raises(ValueError, match="source checkout"):
        exporter().fresh_output(data / "new", code, data)
    (data / ".git/HEAD").unlink()
    (data / "old").mkdir()
    with pytest.raises(FileExistsError):
        exporter().fresh_output(data / "old", code, data)


def test_output_under_source_or_outside_data_rejected(tmp_path):
    code = tmp_path / "code"
    code.mkdir()
    data = tmp_path / "data"
    data.mkdir()
    for output in [code / "new", tmp_path / "elsewhere"]:
        with pytest.raises(ValueError):
            exporter().fresh_output(output, code, data)
