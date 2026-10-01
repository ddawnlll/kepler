import pytest
from factory.enqueue import enqueue, latest


def test_append_only_and_latest(tmp_path):
    q = tmp_path / "q.jsonl"
    i = enqueue("sekreter", "A", "directive", "funding sinyalini 4h'te dene", path=q)
    enqueue("mudur", "A", "result", "bitti", id=i, status="done", path=q)
    assert len(q.read_text().splitlines()) == 2          # silme/ezme yok
    assert latest(q)[i]["status"] == "done" and latest(q)[i]["text"] == "bitti"


@pytest.mark.parametrize("type_,status", [("A", "open"), ("B", "needs_approval"), ("C", "needs_human")])
def test_requests_need_the_right_approval(tmp_path, type_, status):
    q = tmp_path / "q.jsonl"
    i = enqueue("sekreter", type_, "request", "x", status="done", path=q)  # ajan statüyü kendi veremez
    assert latest(q)[i]["status"] == status


def test_rejects_unknown_sender(tmp_path):
    with pytest.raises(ValueError):
        enqueue("hacker", "A", "directive", "x", path=tmp_path / "q.jsonl")
