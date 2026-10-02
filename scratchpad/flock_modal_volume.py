"""Read-only ledger audit helper: locks only an isolated scratchpad file on Modal.

Run with the Modal SDK and existing environment credentials. No ledger/evaluate
imports, writes, deploys, or secret output. Test artifacts remain in scratchpad.
"""
import argparse
import concurrent.futures
import inspect
import io
import json
import time
import uuid
from pathlib import Path

import modal


def worker(path, start_at, hold_seconds, role):
    import fcntl
    import hashlib
    import json
    import os
    import time

    report = {"role": role, "pid": os.getpid(), "path": path}
    try:
        with open(path, "r+") as lock:
            report["file_sha256"] = hashlib.sha256(lock.read().encode()).hexdigest()
            while time.time() < start_at:
                time.sleep(min(0.25, start_at - time.time()))
            report["attempt_at"] = time.time()
            try:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
                report["acquired_at"] = time.time()
                report["acquired"] = True
            except BlockingIOError:
                report["acquired"] = False
            if report["acquired"]:
                with open(path, "r+") as second:
                    try:
                        fcntl.flock(second, fcntl.LOCK_EX | fcntl.LOCK_NB)
                        report["same_container_second_open_blocked"] = False
                        fcntl.flock(second, fcntl.LOCK_UN)
                    except BlockingIOError:
                        report["same_container_second_open_blocked"] = True
                time.sleep(hold_seconds)
                report["released_at"] = time.time()
                fcntl.flock(lock, fcntl.LOCK_UN)
    except Exception as exc:
        report["error_type"] = type(exc).__name__
        report["error"] = str(exc)
    print(json.dumps(report), flush=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default="reports/trial_inventory_data/flock.json")
    parser.add_argument("--rounds", type=int, default=2)
    args = parser.parse_args()
    app = modal.App.lookup("kepler-audits", create_if_missing=False)
    volume = modal.Volume.from_name("kepler-data", create_if_missing=False)
    image = modal.Image.debian_slim(python_version="3.12").pip_install("duckdb", "pandas", "pyarrow", "numpy")
    runs = []
    for round_index in range(args.rounds):
        run_id = f"flock_{round_index}_{uuid.uuid4().hex}"
        remote_path = f"scratchpad/{run_id}/shared.lock"
        with volume.batch_upload() as batch:
            batch.put_file(io.BytesIO(b"kepler isolated flock probe\n"), remote_path)
        start_at = time.time() + 30
        containers = []
        for role in ("A", "B"):
            source = inspect.getsource(worker) + f"\nworker({('/data/' + remote_path)!r}, {start_at!r}, 12, {role!r})\n"
            sandbox = modal.Sandbox.create("python", "-c", source, app=app, image=image,
                                          volumes={"/data": volume}, timeout=120, cpu=0.25, memory=256)
            containers.append((role, sandbox))
        def collect(pair):
            role, sandbox = pair
            sandbox.wait()
            result = json.loads(sandbox.stdout.read())
            result["sandbox_id"] = sandbox.object_id
            result["stderr"] = sandbox.stderr.read()
            return result
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
            results = list(executor.map(collect, containers))
        winners = [r for r in results if r.get("acquired")]
        overlap = len(winners) == 2 and max(r["acquired_at"] for r in winners) < min(r["released_at"] for r in winners)
        valid = (len({r.get("file_sha256") for r in results}) == 1
                 and all("error" not in r for r in results)
                 and all(r["attempt_at"] < start_at + 10 for r in results))
        runs.append({"round": round_index, "shared_path": remote_path, "scheduled_at": start_at,
                     "containers": results, "valid_concurrent_attempt": valid,
                     "overlapping_exclusive_locks": overlap,
                     "cross_container_exclusion_pass": valid and len(winners) == 1})
    output = {"volume": "kepler-data", "runs": runs,
              "pass": all(r["cross_container_exclusion_pass"] for r in runs),
              "ledger_untouched": True, "test_files_retained": True}
    path = Path(args.out)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(output, indent=2) + "\n")
    print(json.dumps({"pass": output["pass"], "rounds": len(runs), "output": str(path)}))


if __name__ == "__main__":
    main()
