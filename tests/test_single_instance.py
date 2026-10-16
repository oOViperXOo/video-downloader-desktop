from single_instance import SingleInstance
from test_process import app


def test_repeat_launch_activates_existing_and_lock_releases(tmp_path):
    first=SingleInstance(tmp_path);second=SingleInstance(tmp_path);third=SingleInstance(tmp_path)
    activated=[]
    try:
        assert first.acquire()
        first.callback=lambda:activated.append(True)
        assert not second.acquire()
        for _ in range(5):app.processEvents()
        assert activated==[True]
        first.close()
        assert third.acquire()
    finally:
        first.close();third.close()
