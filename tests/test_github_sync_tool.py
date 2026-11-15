"""Contract tests for the safe GitHub transfer card and async endpoint."""

import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "SABLON_V2_MIMARI"))
from SABLON_V2_MIMARI import app as mod


def _client(monkeypatch):
    mod.app.config["TESTING"] = False
    mod.DB_STARTUP_AUDIT = {"ready": False, "reason": "DB_NOT_READY"}
    monkeypatch.setattr(mod, "_loopback_check", lambda request, testing=False: None)
    return mod.app.test_client()


def test_professional_tools_has_real_github_sync_card_and_packaged_scripts():
    html = (ROOT / "SABLON_V2_MIMARI" / "templates" / "tools.html").read_text(encoding="utf-8")
    assert "GitHub'a Aktar" in html
    assert "/api/github-sync/info" in html
    assert "/api/github-sync/transfer" in html
    assert "window.confirm" in html
    assert (ROOT / "CODEX_GITHUB_CANLI_COMMIT_ESITLE.ps1").is_file()
    assert (ROOT / "CODEX_GITHUB_CANLI_COMMIT_ESITLE.bat").is_file()


def test_github_info_reports_target_and_local_commit(monkeypatch):
    values = {
        ("rev-parse", "HEAD"): "a" * 40,
        ("show", "-s", "--format=%s", "HEAD"): "safe checkpoint",
        ("symbolic-ref", "--quiet", "--short", "HEAD"): "epic/template-intelligence-v1",
        ("status", "--porcelain"): " M local.py\n?? ignored.tmp\n",
    }
    monkeypatch.setattr(mod, "_github_sync_git", lambda *args: values.get(args, ""))
    c = _client(monkeypatch)
    response = c.get("/api/github-sync/info", base_url="http://127.0.0.1:8080")
    assert response.status_code == 200
    body = response.json
    assert body["connection"]["branch"] == "codex/active-source-sync-20261103"
    assert body["local_commit"]["short_sha"] == "a" * 12
    assert body["local_commit"]["working_tree_changes"] == 2
    assert body["safety"]["auto_commit"] is False


def test_github_transfer_requires_confirmation_and_prevents_duplicate(monkeypatch):
    c = _client(monkeypatch)
    denied = c.post("/api/github-sync/transfer", json={"confirmed": False}, base_url="http://127.0.0.1:8080")
    assert denied.status_code == 400
    with mod._GITHUB_SYNC_LOCK:
        mod._GITHUB_SYNC_ACTIVE = "already-running"
        mod._GITHUB_SYNC_JOBS["already-running"] = {"status": "RUNNING"}
    try:
        busy = c.post("/api/github-sync/transfer", json={"confirmed": True}, base_url="http://127.0.0.1:8080")
        assert busy.status_code == 409
        assert busy.json["code"] == "SYNC_BUSY"
    finally:
        with mod._GITHUB_SYNC_LOCK:
            mod._GITHUB_SYNC_ACTIVE = None
            mod._GITHUB_SYNC_JOBS.pop("already-running", None)


def test_github_transfer_runs_async_and_returns_sha_and_report(monkeypatch):
    class FakeProcess:
        stdout = iter([
            "[1/7] Yerel commit okunuyor\n",
            "CODEX_SYNC_COMMIT_SHA=" + "b" * 40 + "\n",
            "CODEX_SYNC_RESULT=COMMITTED\n",
            "CODEX_SYNC_PR_URL=https://github.com/example/repo/pull/83\n",
        ])

        def wait(self):
            return 0

    monkeypatch.setattr(mod.subprocess, "Popen", lambda *args, **kwargs: FakeProcess())
    c = _client(monkeypatch)
    response = c.post("/api/github-sync/transfer", json={"confirmed": True}, base_url="http://127.0.0.1:8080")
    assert response.status_code == 202
    job_id = response.json["job_id"]
    for _ in range(20):
        status = c.get("/api/github-sync/status/" + job_id, base_url="http://127.0.0.1:8080").json
        if status.get("status") != "RUNNING":
            break
        time.sleep(0.01)
    assert status["status"] == "SUCCEEDED"
    assert status["commit_sha"] == "b" * 40
    assert status["pull_request"].endswith("/pull/83")
    assert status["technical_report_path"]


def test_packaged_script_keeps_safe_transfer_invariants():
    script = (ROOT / "CODEX_GITHUB_CANLI_COMMIT_ESITLE.ps1").read_text(encoding="utf-8")
    assert "$Root = (Resolve-Path (Join-Path $PSScriptRoot '.')).Path" in script
    assert "GIT_INDEX_FILE" in script
    assert "commit-tree" in script
    assert "force" not in script.casefold() or "Force olmayan" in script
    assert "CODEX_SYNC_COMMIT_SHA=" in script
    assert "ayarlar\\.json" in script
