from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


def test_workspace_root_defaults_under_sim_dir(tmp_path, monkeypatch):
    monkeypatch.setenv("SIM_DIR", str(tmp_path / ".sim"))

    from sim.workspace import workspace_root

    root = workspace_root()

    assert root == tmp_path / ".sim" / "workspace"
    assert root.is_dir()


@pytest.mark.parametrize(
    "remote_path",
    [
        "../secret.txt",
        "nested/../../secret.txt",
        "/tmp/secret.txt",
        r"C:\Users\cq\secret.txt",
        "bad\x00name.txt",
        "",
        ".",
    ],
)
def test_resolve_workspace_path_rejects_unsafe_paths(tmp_path, remote_path):
    from sim.workspace import WorkspacePathError, resolve_workspace_path

    with pytest.raises(WorkspacePathError):
        resolve_workspace_path(tmp_path / "workspace", remote_path)


def test_resolve_workspace_path_allows_nested_relative_paths(tmp_path):
    from sim.workspace import resolve_workspace_path

    root = tmp_path / "workspace"

    assert resolve_workspace_path(root, "inputs/model.gds") == root / "inputs" / "model.gds"


def test_resolve_workspace_path_rejects_symlink_escape(tmp_path):
    from sim.workspace import WorkspacePathError, resolve_workspace_path

    root = tmp_path / "workspace"
    root.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    (root / "link").symlink_to(outside, target_is_directory=True)

    with pytest.raises(WorkspacePathError):
        resolve_workspace_path(root, "link/secret.txt")


def test_list_workspace_files_reports_relative_files(tmp_path):
    from sim.workspace import list_workspace_files

    root = tmp_path / "workspace"
    (root / "inputs").mkdir(parents=True)
    (root / "inputs" / "a.gds").write_bytes(b"abc")
    (root / "notes.txt").write_text("hello", encoding="utf-8")

    rows = list_workspace_files(root)

    assert rows == [
        {"path": "inputs/a.gds", "kind": "file", "size": 3},
        {"path": "notes.txt", "kind": "file", "size": 5},
    ]


def test_workspace_list_endpoint_uses_sim_dir_workspace(tmp_path, monkeypatch):
    monkeypatch.setenv("SIM_DIR", str(tmp_path / ".sim"))
    root = tmp_path / ".sim" / "workspace"
    (root / "inputs").mkdir(parents=True)
    (root / "inputs" / "a.gds").write_bytes(b"abc")

    from sim import server

    client = TestClient(server.app)
    response = client.get("/workspace/list")

    assert response.status_code == 200
    assert response.json() == {
        "ok": True,
        "data": {
            "path": ".",
            "files": [{"path": "inputs/a.gds", "kind": "file", "size": 3}],
        },
    }


def test_workspace_upload_download_and_delete(tmp_path, monkeypatch):
    monkeypatch.setenv("SIM_DIR", str(tmp_path / ".sim"))

    from sim import server

    client = TestClient(server.app)
    upload = client.post(
        "/files/upload",
        data={"path": "inputs/a.txt"},
        files={"file": ("a.txt", b"hello", "text/plain")},
    )
    assert upload.status_code == 200
    assert upload.json()["data"]["path"] == "inputs/a.txt"
    assert upload.json()["data"]["size"] == 5

    duplicate = client.post(
        "/files/upload",
        data={"path": "inputs/a.txt"},
        files={"file": ("a.txt", b"again", "text/plain")},
    )
    assert duplicate.status_code == 409

    download = client.get("/files/download", params={"path": "inputs/a.txt"})
    assert download.status_code == 200
    assert download.content == b"hello"

    deleted = client.delete("/files/delete", params={"path": "inputs/a.txt"})
    assert deleted.status_code == 200
    assert deleted.json()["data"] == {"path": "inputs/a.txt", "deleted": True}


def test_upload_rejects_files_larger_than_limit(tmp_path, monkeypatch):
    monkeypatch.setenv("SIM_DIR", str(tmp_path / ".sim"))
    monkeypatch.setenv("SIM_WORKSPACE_MAX_UPLOAD_BYTES", "4")

    from sim import server

    client = TestClient(server.app)

    response = client.post(
        "/files/upload",
        data={"path": "too-large.txt"},
        files={"file": ("too-large.txt", b"hello", "text/plain")},
    )

    assert response.status_code == 413
    assert "upload too large" in response.json()["detail"]


def test_file_endpoints_reject_workspace_escape(tmp_path, monkeypatch):
    monkeypatch.setenv("SIM_DIR", str(tmp_path / ".sim"))

    from sim import server

    client = TestClient(server.app)

    response = client.get("/files/download", params={"path": "../secret.txt"})

    assert response.status_code == 400
    assert "workspace" in response.json()["detail"]


def test_session_client_transfers_files(tmp_path, monkeypatch):
    monkeypatch.setenv("SIM_DIR", str(tmp_path / ".sim"))

    from sim import server
    from sim.session import SessionClient

    test_client = TestClient(server.app)

    class InProcessClient:
        def __init__(self, *args, **kwargs):
            pass

        def __enter__(self):
            return test_client

        def __exit__(self, exc_type, exc, tb):
            return False

    monkeypatch.setattr("sim.session._httpx_client", InProcessClient)
    local = tmp_path / "local.txt"
    local.write_text("hello", encoding="utf-8")
    downloaded = tmp_path / "downloaded.txt"

    client = SessionClient()

    assert client.put(local, "inputs/local.txt")["ok"] is True
    assert client.ls()["data"]["files"] == [
        {"path": "inputs/local.txt", "kind": "file", "size": 5}
    ]
    assert client.get("inputs/local.txt", downloaded)["ok"] is True
    assert downloaded.read_text(encoding="utf-8") == "hello"
    assert client.rm("inputs/local.txt")["ok"] is True


def test_cli_put_get_ls_rm_roundtrip(tmp_path, monkeypatch):
    monkeypatch.setenv("SIM_DIR", str(tmp_path / ".sim"))

    from sim import server
    from sim.cli import main

    test_client = TestClient(server.app)

    class InProcessClient:
        def __init__(self, *args, **kwargs):
            pass

        def __enter__(self):
            return test_client

        def __exit__(self, exc_type, exc, tb):
            return False

    monkeypatch.setattr("sim.session._httpx_client", InProcessClient)

    local = tmp_path / "local.txt"
    local.write_text("hello", encoding="utf-8")
    downloaded = tmp_path / "downloaded.txt"

    from click.testing import CliRunner

    runner = CliRunner()
    put_result = runner.invoke(main, ["put", str(local), "inputs/local.txt"])
    assert put_result.exit_code == 0, put_result.output
    assert "uploaded" in put_result.output

    ls_result = runner.invoke(main, ["ls"])
    assert ls_result.exit_code == 0, ls_result.output
    assert "inputs/local.txt" in ls_result.output

    get_result = runner.invoke(main, ["get", "inputs/local.txt", str(downloaded)])
    assert get_result.exit_code == 0, get_result.output
    assert downloaded.read_text(encoding="utf-8") == "hello"

    rm_result = runner.invoke(main, ["rm", "inputs/local.txt"])
    assert rm_result.exit_code == 0, rm_result.output
    assert "deleted" in rm_result.output
