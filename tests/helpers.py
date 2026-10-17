import time


def wait_for_job(client, id, timeout=3):
    """Detached execution is not complete merely because POST returned."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        response = client.get(f"/v1/cv-jobs/{id}")
        assert response.status_code == 200
        job = response.json()
        if job["status"] in ("succeeded", "failed", "cancelled"):
            return job
        time.sleep(0.005)
    raise AssertionError(f"Job {id} did not settle within {timeout}s")
