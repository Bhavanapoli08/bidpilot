"""
Integration tests: monitoring scan -> discovered -> import -> bid workflow.
Uses the SAMPLE connector so no network access is required.
"""


def _create_sample_source(client, headers):
    return client.post(
        "/api/monitoring/sources",
        headers=headers,
        json={"name": "Demo Portal", "source_type": "sample"},
    )


def test_scan_creates_discovered_tenders(client, auth_headers):
    assert _create_sample_source(client, auth_headers).status_code == 200

    scan = client.post("/api/monitoring/scan", headers=auth_headers)
    assert scan.status_code == 200
    body = scan.json()
    assert body["sources_scanned"] == 1
    assert body["new_discovered"] > 0

    # Re-scanning must be idempotent (dedup by external_id).
    scan2 = client.post("/api/monitoring/scan", headers=auth_headers)
    assert scan2.json()["new_discovered"] == 0

    discovered = client.get("/api/monitoring/discovered", headers=auth_headers).json()
    assert len(discovered) == body["new_discovered"]


def test_import_discovered_into_bid_and_advance(client, auth_headers):
    _create_sample_source(client, auth_headers)
    client.post("/api/monitoring/scan", headers=auth_headers)

    discovered = client.get("/api/monitoring/discovered", headers=auth_headers).json()
    target = discovered[0]

    imported = client.post(
        f"/api/monitoring/discovered/{target['id']}/import", headers=auth_headers
    )
    assert imported.status_code == 200
    bid = imported.json()
    assert bid["stage"] == "identified"
    assert bid["title"] == target["title"]

    # Discovered item is now marked imported and drops out of the "new" list.
    new_list = client.get("/api/monitoring/discovered", headers=auth_headers).json()
    assert all(d["id"] != target["id"] for d in new_list)

    # Advance the bid through the pipeline.
    moved = client.patch(
        f"/api/bids/{bid['id']}/stage",
        headers=auth_headers,
        json={"stage": "submitted", "note": "Proposal sent"},
    )
    assert moved.status_code == 200
    assert moved.json()["stage"] == "submitted"

    detail = client.get(f"/api/bids/{bid['id']}", headers=auth_headers).json()
    event_types = {e["event_type"] for e in detail["events"]}
    assert {"created", "stage_change"} <= event_types


def test_terminal_stage_sets_decided_at(client, auth_headers):
    bid = client.post(
        "/api/bids", headers=auth_headers, json={"title": "Manual pursuit"}
    ).json()
    assert bid["decided_at"] is None

    won = client.patch(
        f"/api/bids/{bid['id']}/stage", headers=auth_headers, json={"stage": "won"}
    ).json()
    assert won["decided_at"] is not None


def test_invalid_stage_rejected(client, auth_headers):
    bid = client.post(
        "/api/bids", headers=auth_headers, json={"title": "X"}
    ).json()
    resp = client.patch(
        f"/api/bids/{bid['id']}/stage", headers=auth_headers, json={"stage": "nonsense"}
    )
    assert resp.status_code == 400


def test_calendar_lists_bid_deadlines(client, auth_headers):
    _create_sample_source(client, auth_headers)
    client.post("/api/monitoring/scan", headers=auth_headers)
    discovered = client.get("/api/monitoring/discovered", headers=auth_headers).json()
    client.post(
        f"/api/monitoring/discovered/{discovered[0]['id']}/import", headers=auth_headers
    )

    cal = client.get("/api/bids/calendar?days=365", headers=auth_headers)
    assert cal.status_code == 200
    assert len(cal.json()) >= 1
    assert "days_remaining" in cal.json()[0]
