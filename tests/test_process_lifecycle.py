import asyncio
import sys
from pathlib import Path

import pytest

from f8pysdk.specs import F8RuntimeNode
from f8proclauncher import proclauncher_service_node as launcher


def test_managed_process_close_reaps_child_and_removes_pidfile(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    pidfile = tmp_path / "child.json"
    monkeypatch.setattr(launcher, "_pidfile_path_for", lambda argv: pidfile)

    async def scenario() -> None:
        node = launcher.ProcLauncherServiceNode(
            node_id="test", node=F8RuntimeNode(nodeId="test", serviceId="test", serviceClass="f8.proclauncher"),
            initial_state={"detached": False},
        )
        node._pidfile = pidfile
        await node._spawn([sys.executable, "-c", "import time; time.sleep(30)"], detached=False)
        child = node._proc
        assert child is not None and child.poll() is None
        assert pidfile.is_file()
        try:
            await node.close()
            assert child.poll() is not None
            assert not pidfile.exists()
        finally:
            if child.poll() is None:
                child.kill()
            child.wait(timeout=5)

    asyncio.run(scenario())


def test_pidfile_corruption_is_reported(tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
    path = tmp_path / "invalid.json"
    path.write_text("invalid")
    with caplog.at_level("DEBUG"):
        assert launcher._read_pid_record(path) is None
    assert caplog.records[0].exc_info is not None


@pytest.mark.parametrize("value,expected", [(True, True), (0, False), (1, True), ("on", True), (2, None), (1.0, None)])
def test_boolean_validation_keeps_launcher_contract(value: object, expected: bool | None) -> None:
    assert launcher._coerce_bool(value) is expected
