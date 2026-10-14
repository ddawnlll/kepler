"""Thin broker client for Hermes. Tool restrictions are not authorization boundaries."""
from factory.broker import call


def submit(text, type_, kind="request", *, delivery_id, payload=None, sender="sekreter"):
    return call({"op": "enqueue", "from": sender, "type": type_, "kind": kind, "text": text,
                 "payload": payload or {}, "idempotency_key": "telegram:" + str(delivery_id)})


def query_state():
    return call({"op": "status"})


def pause(kill_running=False):
    return call({"op": "stop" if kill_running else "pause"})
