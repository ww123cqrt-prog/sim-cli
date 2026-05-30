from __future__ import annotations

import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path


PLUGIN_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PLUGIN_DIR))

from sim_plugin_cmd import CmdDriver  # noqa: E402


class FakeMsvcrt:
    def __init__(self, answers: list[str]):
        self._chars = list("".join(answer + "\r" for answer in answers))
        self._lock = threading.Lock()
        self._allow_input = threading.Event()
        self._polled = threading.Event()

    def allow_input(self) -> None:
        self._allow_input.set()

    def wait_until_polled(self) -> None:
        assert self._polled.wait(1), "confirmation prompt did not start polling"

    def kbhit(self) -> bool:
        self._polled.set()
        if not self._allow_input.is_set():
            return False
        with self._lock:
            return bool(self._chars)

    def getwch(self) -> str:
        with self._lock:
            return self._chars.pop(0)


def _pending_session(driver: CmdDriver) -> tuple[str, str]:
    result = driver.launch()
    data = result["data"]
    return data["session_id"], data["auth_token"]


def test_duplicate_confirm_for_same_session_shares_one_prompt(monkeypatch, capsys):
    fake_msvcrt = FakeMsvcrt(["y"])
    monkeypatch.setitem(sys.modules, "msvcrt", fake_msvcrt)
    driver = CmdDriver(require_confirm=True)
    session_id, token = _pending_session(driver)

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [
            pool.submit(driver.confirm_session, session_id, token, timeout=1),
            pool.submit(driver.confirm_session, session_id, token, timeout=1),
        ]
        fake_msvcrt.wait_until_polled()
        time.sleep(0.1)
        assert capsys.readouterr().out.count("[APPROVAL REQUIRED]") == 1

        fake_msvcrt.allow_input()
        results = [future.result(timeout=2) for future in futures]

    assert all(result["ok"] for result in results)


def test_confirm_prompts_are_serialized_across_sessions(monkeypatch, capsys):
    fake_msvcrt = FakeMsvcrt(["y", "y"])
    monkeypatch.setitem(sys.modules, "msvcrt", fake_msvcrt)
    driver = CmdDriver(require_confirm=True)
    first_session_id, first_token = _pending_session(driver)
    second_session_id, second_token = _pending_session(driver)

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [
            pool.submit(driver.confirm_session, first_session_id, first_token, timeout=1),
            pool.submit(driver.confirm_session, second_session_id, second_token, timeout=1),
        ]
        fake_msvcrt.wait_until_polled()
        time.sleep(0.1)
        assert capsys.readouterr().out.count("[APPROVAL REQUIRED]") == 1

        fake_msvcrt.allow_input()
        results = [future.result(timeout=2) for future in futures]

    assert all(result["ok"] for result in results)
