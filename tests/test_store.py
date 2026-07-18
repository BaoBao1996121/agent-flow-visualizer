from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
import os
import threading

import pytest

from anthill.schema import (
    AgentRuntimeEvent,
    EventSource,
    Evidence,
    EvidenceLevel,
    SourceFidelity,
)
from anthill.store import (
    CorruptLedgerError,
    DuplicateEventError,
    JsonlEventStore,
    RunAlreadyExistsError,
)


def event(
    run_id: str,
    event_id: str,
    event_type: str = "test.observed",
    *,
    payload: dict | None = None,
):
    return AgentRuntimeEvent(
        event_id=event_id,
        event_type=event_type,
        run_id=run_id,
        source=EventSource(adapter="tests", fidelity=SourceFidelity.NATIVE),
        evidence=Evidence(level=EvidenceLevel.OBSERVED, confidence=1.0),
        payload=payload or {},
    )


def test_append_assigns_contiguous_sequence_and_hash_chain(tmp_path):
    store = JsonlEventStore(tmp_path)
    stored = store.append_many(
        [event("run-1", "evt-1"), event("run-1", "evt-2")]
    )

    assert [item.clock.ingest_seq for item in stored] == [0, 1]
    assert stored[1].integrity.previous_event_hash == stored[0].integrity.event_hash
    assert store.verify_run("run-1")["valid"] is True


def test_duplicate_event_is_rejected_without_partial_batch(tmp_path):
    store = JsonlEventStore(tmp_path)
    store.append(event("run-1", "evt-1"))

    with pytest.raises(DuplicateEventError):
        store.append_many(
            [event("run-1", "evt-2"), event("run-1", "evt-1")]
        )

    assert [item.event_id for item in store.read_run("run-1")] == ["evt-1"]


def test_require_empty_creates_one_complete_batch_and_rejects_a_second(tmp_path):
    store = JsonlEventStore(tmp_path)

    created = store.append_many(
        [event("new-run", "evt-1"), event("new-run", "evt-2")],
        require_empty=True,
    )

    assert [item.clock.ingest_seq for item in created] == [0, 1]
    with pytest.raises(RunAlreadyExistsError):
        store.append_many(
            [event("new-run", "different-event-id")],
            require_empty=True,
        )
    assert [item.event_id for item in store.read_run("new-run")] == [
        "evt-1",
        "evt-2",
    ]


def test_concurrent_appends_keep_a_single_contiguous_chain(tmp_path):
    store = JsonlEventStore(tmp_path)

    with ThreadPoolExecutor(max_workers=8) as pool:
        list(
            pool.map(
                store.append,
                [event("run-1", f"evt-{index}") for index in range(80)],
            )
        )

    events = list(store.read_run("run-1"))
    assert len(events) == 80
    assert [item.clock.ingest_seq for item in events] == list(range(80))
    assert store.verify_run("run-1")["valid"] is True


def test_tampered_payload_breaks_integrity_verification(tmp_path):
    store = JsonlEventStore(tmp_path)
    stored = store.append(event("run-1", "evt-1"))
    ledger = next(tmp_path.glob("*/events.jsonl"))
    payload = json.loads(ledger.read_text(encoding="utf-8"))
    payload["summary"] = "tampered"
    ledger.write_text(json.dumps(payload) + "\n", encoding="utf-8")

    verification = JsonlEventStore(tmp_path).verify_run("run-1")
    assert verification["valid"] is False
    assert any("hash does not match" in item for item in verification["errors"])
    assert stored.event_id == "evt-1"


def test_runs_are_partitioned_and_queryable(tmp_path):
    store = JsonlEventStore(tmp_path)
    store.append(event("run-a", "evt-a", "agent.spawned"))
    store.append(event("run-b", "evt-b", "tool.execution.started"))

    manifests = store.list_runs()
    assert {item["run_id"] for item in manifests} == {"run-a", "run-b"}
    assert [item.event_id for item in store.read_run("run-a")] == ["evt-a"]
    assert [
        item.event_id
        for item in store.read_run("run-b", event_types=["tool.execution.started"])
    ] == ["evt-b"]


def test_manifest_is_reconstructed_from_authoritative_ledger(tmp_path):
    store = JsonlEventStore(tmp_path)
    store.append(event("run-1", "evt-1"))
    manifest_path = next(tmp_path.glob("*/manifest.json"))
    manifest_path.write_text("{broken", encoding="utf-8")

    manifest = JsonlEventStore(tmp_path).get_manifest("run-1")
    assert manifest is not None
    assert manifest["run_id"] == "run-1"
    assert manifest["event_count"] == 1
    assert manifest["last_event_type"] == "test.observed"


def test_append_repairs_a_torn_manifest_from_the_complete_ledger(tmp_path):
    store = JsonlEventStore(tmp_path)
    store.append_many(
        [
            event(
                "repair-run",
                "repair-start",
                "run.started",
                payload={"title": "Repairable run"},
            ),
            event(
                "repair-run",
                "repair-complete",
                "run.completed",
                payload={"status": "success"},
            ),
        ]
    )
    manifest_path = next(tmp_path.glob("*/manifest.json"))
    manifest_path.write_text("{broken", encoding="utf-8")

    store.append(event("repair-run", "repair-artifact", "artifact.created"))

    manifest = store.get_manifest("repair-run")
    assert manifest["run_status"] == "completed"
    assert manifest["event_count"] == 3
    assert manifest["title"] == "Repairable run"
    assert manifest["source_adapter"] == "tests"
    events = list(store.read_run("repair-run"))
    assert manifest["created_at"] == events[0].clock.observed_at.isoformat()
    assert manifest["updated_at"] == events[-1].clock.observed_at.isoformat()
    assert manifest["last_event_type"] == "artifact.created"


def test_append_repairs_a_valid_but_stale_manifest_from_the_complete_ledger(tmp_path):
    store = JsonlEventStore(tmp_path)
    store.append(event("stale-run", "start", "run.started"))
    manifest_path = next(tmp_path.glob("*/manifest.json"))
    stale_manifest = manifest_path.read_text(encoding="utf-8")
    store.append(
        event(
            "stale-run",
            "complete",
            "run.completed",
            payload={"status": "success"},
        )
    )
    manifest_path.write_text(stale_manifest, encoding="utf-8")

    restarted = JsonlEventStore(tmp_path)
    restarted.append(event("stale-run", "artifact", "artifact.created"))

    manifest = restarted.get_manifest("stale-run")
    assert manifest["event_count"] == 3
    assert manifest["run_status"] == "completed"
    assert manifest["last_event_type"] == "artifact.created"


def test_run_listing_repairs_missing_and_wrong_shape_manifests(tmp_path):
    store = JsonlEventStore(tmp_path)
    store.append(event("repair-list", "start", "run.started"))
    manifest_path = next(tmp_path.glob("*/manifest.json"))
    manifest_path.write_text("[]", encoding="utf-8")

    manifests = JsonlEventStore(tmp_path).list_runs()

    assert len(manifests) == 1
    assert manifests[0]["run_id"] == "repair-list"
    assert manifests[0]["run_status"] == "running"
    assert json.loads(manifest_path.read_text(encoding="utf-8"))["event_count"] == 1

    manifest_path.unlink()
    rebuilt = JsonlEventStore(tmp_path).list_runs()
    assert rebuilt[0]["run_id"] == "repair-list"
    assert manifest_path.exists()


def test_run_listing_repairs_semantically_forged_manifest_cache_fields(tmp_path):
    store = JsonlEventStore(tmp_path)
    store.append(
        event(
            "semantic-cache",
            "start",
            "run.started",
            payload={"title": "Ledger truth"},
        )
    )
    manifest_path = next(tmp_path.glob("*/manifest.json"))
    forged = json.loads(manifest_path.read_text(encoding="utf-8"))
    forged["run_status"] = "completed"
    forged["title"] = "Forged cache"
    forged["source_adapter"] = "forged.adapter"
    manifest_path.write_text(json.dumps(forged), encoding="utf-8")

    manifest = JsonlEventStore(tmp_path).list_runs()[0]

    assert manifest["run_status"] == "running"
    assert manifest["title"] == "Ledger truth"
    assert manifest["source_adapter"] == "tests"
    assert "_cache_checksum" not in manifest


def test_append_repairs_malformed_manifest_fields_without_partial_failure(tmp_path):
    store = JsonlEventStore(tmp_path)
    store.append(event("malformed-fields", "start", "run.started"))
    manifest_path = next(tmp_path.glob("*/manifest.json"))
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["event_count"] = "bad"
    manifest["run_status"] = {"not": "a status"}
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    restarted = JsonlEventStore(tmp_path)
    restarted.append(event("malformed-fields", "artifact", "artifact.created"))

    repaired = restarted.get_manifest("malformed-fields")
    assert repaired["event_count"] == 2
    assert repaired["run_status"] == "running"
    assert [item.event_id for item in restarted.read_run("malformed-fields")] == [
        "start",
        "artifact",
    ]


def test_get_manifest_repairs_legacy_manifest_missing_run_status(tmp_path):
    store = JsonlEventStore(tmp_path)
    store.append(event("legacy-run", "start", "run.started"))
    manifest_path = next(tmp_path.glob("*/manifest.json"))
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest.pop("run_status")
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    repaired = JsonlEventStore(tmp_path).get_manifest("legacy-run")

    assert repaired["run_status"] == "running"


def test_manifest_repair_is_serialized_with_concurrent_append(tmp_path, monkeypatch):
    store = JsonlEventStore(tmp_path)
    store.append(event("locked-run", "start", "run.started"))
    manifest_path = next(tmp_path.glob("*/manifest.json"))
    manifest_path.write_text("{broken", encoding="utf-8")
    original_rebuild = store._manifest_from_ledger
    rebuild_started = threading.Event()
    release_rebuild = threading.Event()
    rebuild_calls = 0
    rebuild_calls_lock = threading.Lock()

    def slow_rebuild(run_id):
        nonlocal rebuild_calls
        with rebuild_calls_lock:
            rebuild_calls += 1
            call_number = rebuild_calls
        manifest = original_rebuild(run_id)
        if call_number == 1:
            rebuild_started.set()
            assert release_rebuild.wait(2)
        return manifest

    monkeypatch.setattr(store, "_manifest_from_ledger", slow_rebuild)
    append_finished = threading.Event()

    def append_terminal():
        store.append(
            event(
                "locked-run",
                "complete",
                "run.completed",
                payload={"status": "success"},
            )
        )
        append_finished.set()

    with ThreadPoolExecutor(max_workers=2) as pool:
        repair = pool.submit(store.get_manifest, "locked-run")
        assert rebuild_started.wait(1)
        append = pool.submit(append_terminal)
        append_finished.wait(0.2)
        release_rebuild.set()
        repair.result(timeout=2)
        append.result(timeout=2)

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["event_count"] == 2
    assert manifest["run_status"] == "completed"
    assert manifest["last_event_hash"] == store.verify_run("locked-run")["last_event_hash"]


def test_append_rejects_a_ledger_with_a_sequence_gap(tmp_path):
    store = JsonlEventStore(tmp_path)
    store.append_many(
        [event("gap-run", "event-0"), event("gap-run", "event-1"), event("gap-run", "event-2")]
    )
    ledger = next(tmp_path.glob("*/events.jsonl"))
    lines = ledger.read_text(encoding="utf-8").splitlines()
    ledger.write_text(f"{lines[0]}\n{lines[2]}\n", encoding="utf-8")

    with pytest.raises(CorruptLedgerError, match="sequence 2 found; expected 1"):
        JsonlEventStore(tmp_path).append(event("gap-run", "event-3"))

    assert len(ledger.read_text(encoding="utf-8").splitlines()) == 2


def test_append_rejects_a_ledger_with_a_tampered_payload(tmp_path):
    store = JsonlEventStore(tmp_path)
    store.append(event("tampered-run", "event-0", payload={"value": "original"}))
    ledger = next(tmp_path.glob("*/events.jsonl"))
    payload = json.loads(ledger.read_text(encoding="utf-8"))
    payload["payload"]["value"] = "tampered"
    ledger.write_text(json.dumps(payload) + "\n", encoding="utf-8")

    with pytest.raises(CorruptLedgerError, match="hash does not match"):
        JsonlEventStore(tmp_path).append(event("tampered-run", "event-1"))


def test_cached_append_index_is_invalidated_when_the_ledger_changes(tmp_path):
    store = JsonlEventStore(tmp_path)
    store.append(event("cached-tamper", "event-0", payload={"value": "short"}))
    ledger = next(tmp_path.glob("*/events.jsonl"))
    payload = json.loads(ledger.read_text(encoding="utf-8"))
    payload["payload"]["value"] = "tampered-and-longer"
    ledger.write_text(json.dumps(payload) + "\n", encoding="utf-8")

    with pytest.raises(CorruptLedgerError, match="hash does not match"):
        store.append(event("cached-tamper", "event-1"))


def test_append_revalidates_metadata_preserving_same_length_ledger_changes(tmp_path):
    store = JsonlEventStore(tmp_path)
    store.append(event("stealth-tamper", "event-0", payload={"value": "original"}))
    ledger = next(tmp_path.glob("*/events.jsonl"))
    original_stat = ledger.stat()
    original_bytes = ledger.read_bytes()
    tampered_bytes = original_bytes.replace(b'"original"', b'"tampered"')
    assert tampered_bytes != original_bytes
    assert len(tampered_bytes) == len(original_bytes)

    ledger.write_bytes(tampered_bytes)
    os.utime(ledger, ns=(original_stat.st_atime_ns, original_stat.st_mtime_ns))

    with pytest.raises(CorruptLedgerError, match="hash does not match"):
        store.append(event("stealth-tamper", "event-1"))


@pytest.mark.parametrize("retained_line_count", [2, 1, 0])
def test_valid_manifest_head_quarantines_a_truncated_ledger_before_append(
    tmp_path, retained_line_count
):
    store = JsonlEventStore(tmp_path)
    store.append_many(
        [
            event("truncated-run", "start", "run.started"),
            event("truncated-run", "artifact", "artifact.created"),
            event(
                "truncated-run",
                "complete",
                "run.completed",
                payload={"status": "success"},
            ),
        ]
    )
    ledger = next(tmp_path.glob("*/events.jsonl"))
    manifest = next(tmp_path.glob("*/manifest.json"))
    original_manifest = manifest.read_bytes()
    lines = ledger.read_bytes().splitlines(keepends=True)
    ledger.write_bytes(b"".join(lines[:retained_line_count]))
    truncated_ledger = ledger.read_bytes()
    restarted = JsonlEventStore(tmp_path)

    with pytest.raises(CorruptLedgerError) as append_error:
        restarted.append(event("truncated-run", "artifact", "artifact.created"))

    assert append_error.value.error_type == "truncated_ledger"
    assert ledger.read_bytes() == truncated_ledger
    assert manifest.read_bytes() == original_manifest
    with pytest.raises(CorruptLedgerError) as read_error:
        restarted.get_manifest("truncated-run")
    assert read_error.value.error_type == "truncated_ledger"
    listing = restarted.list_runs_with_diagnostics()
    assert listing["items"] == []
    assert listing["discovery_error_count"] == 1
    assert listing["discovery_errors"][0]["error_type"] == "truncated_ledger"


def test_valid_manifest_head_diagnoses_a_deleted_ledger_without_recreating_it(tmp_path):
    store = JsonlEventStore(tmp_path)
    store.append_many(
        [
            event("deleted-ledger", "start", "run.started"),
            event(
                "deleted-ledger",
                "complete",
                "run.completed",
                payload={"status": "success"},
            ),
        ]
    )
    ledger = next(tmp_path.glob("*/events.jsonl"))
    manifest = next(tmp_path.glob("*/manifest.json"))
    original_manifest = manifest.read_bytes()
    ledger.unlink()
    restarted = JsonlEventStore(tmp_path)

    with pytest.raises(CorruptLedgerError) as append_error:
        restarted.append(event("deleted-ledger", "artifact", "artifact.created"))
    assert append_error.value.error_type == "truncated_ledger"
    assert not ledger.exists()
    assert manifest.read_bytes() == original_manifest

    with pytest.raises(CorruptLedgerError) as read_error:
        restarted.get_manifest("deleted-ledger")
    assert read_error.value.error_type == "truncated_ledger"

    listing = restarted.list_runs_with_diagnostics()
    assert listing["items"] == []
    assert listing["discovery_error_count"] == 1
    assert listing["discovery_errors"][0]["error_type"] == "truncated_ledger"


def test_unchanged_ledger_reuses_a_content_verified_append_index(tmp_path, monkeypatch):
    store = JsonlEventStore(tmp_path)
    store.append(event("digest-cache", "event-0"))

    def fail_full_parse(_run_id):
        raise AssertionError("unchanged content should not be parsed again")

    monkeypatch.setattr(store, "_iter_validated_run", fail_full_parse)

    appended = store.append(event("digest-cache", "event-1"))
    assert appended.clock.ingest_seq == 1


def test_append_revalidates_preconstructed_events_without_legacy_context(tmp_path):
    unsafe_run_id = "legacy-\u202espoof"
    payload = event("safe-run", "legacy-event").model_dump(mode="json")
    payload["schema_version"] = "0.1.0"
    payload["run_id"] = unsafe_run_id
    legacy_event = AgentRuntimeEvent.model_validate(
        payload,
        context={"allow_legacy_run_id": True},
    )

    with pytest.raises(ValueError, match="control or format characters"):
        JsonlEventStore(tmp_path).append(legacy_event)

    assert list(tmp_path.glob("*/events.jsonl")) == []


def test_normal_run_listing_does_not_build_the_append_event_id_index(tmp_path, monkeypatch):
    store = JsonlEventStore(tmp_path)
    store.append(event("listing-run", "event-0", "run.started"))
    restarted = JsonlEventStore(tmp_path)

    def fail_index(_run_id):
        raise AssertionError("normal listing must use the lightweight ledger boundary")

    monkeypatch.setattr(restarted, "_index_for", fail_index)

    assert restarted.list_runs()[0]["run_id"] == "listing-run"
    assert restarted._indexes == {}


def test_corrupt_and_misplaced_ledgers_are_diagnosed_without_hiding_healthy_runs(tmp_path):
    store = JsonlEventStore(tmp_path)
    store.append(event("healthy-run", "event-0", "run.started"))
    canonical_ledger = next(tmp_path.glob("*/events.jsonl"))
    misplaced_dir = tmp_path / "misplaced-copy"
    misplaced_dir.mkdir()
    (misplaced_dir / "events.jsonl").write_bytes(canonical_ledger.read_bytes())
    corrupt_dir = tmp_path / "corrupt-copy"
    corrupt_dir.mkdir()
    (corrupt_dir / "events.jsonl").write_text("{broken\n", encoding="utf-8")

    def opaque(name):
        return "ledger:" + hashlib.sha256(name.encode()).hexdigest()[:24]

    result = JsonlEventStore(tmp_path).list_runs_with_diagnostics()

    assert [item["run_id"] for item in result["items"]] == ["healthy-run"]
    assert sorted(result["discovery_errors"], key=lambda item: item["error_type"]) == sorted(
        [
            {"ledger_ref": opaque("corrupt-copy"), "error_type": "invalid_first_event"},
            {"ledger_ref": opaque("misplaced-copy"), "error_type": "misplaced_ledger"},
        ],
        key=lambda item: item["error_type"],
    )


def test_unsafe_legacy_run_id_is_quarantined_from_normal_run_listing(tmp_path):
    store = JsonlEventStore(tmp_path)
    unsafe_run_id = "legacy-\u202espoof"
    payload = event("safe-run", "legacy-event", "run.started").model_dump(mode="json")
    payload["schema_version"] = "0.1.0"
    payload["run_id"] = unsafe_run_id
    legacy_event = AgentRuntimeEvent.model_validate(
        payload,
        context={"allow_legacy_run_id": True},
    ).with_ingest_metadata(ingest_seq=0, previous_event_hash=None)
    run_dir = store._run_dir(unsafe_run_id)
    run_dir.mkdir(parents=True)
    (run_dir / "events.jsonl").write_text(
        legacy_event.to_json_line(),
        encoding="utf-8",
    )

    listing = JsonlEventStore(tmp_path).list_runs_with_diagnostics()

    assert listing["items"] == []
    assert [item["error_type"] for item in listing["discovery_errors"]] == [
        "unsafe_legacy_run_id"
    ]
    assert unsafe_run_id not in json.dumps(listing, ensure_ascii=False)


def test_corrupt_ledger_error_uses_an_opaque_reference_without_rejected_input(tmp_path):
    store = JsonlEventStore(tmp_path)
    store.append(event("private-run", "event-0"))
    ledger = next(tmp_path.glob("*/events.jsonl"))
    secret = "SECRET_REJECTED_LEDGER_INPUT"
    ledger.write_text(
        json.dumps({"schema_version": "0.2.0", "secret": secret}) + "\n",
        encoding="utf-8",
    )

    with pytest.raises(CorruptLedgerError) as captured:
        list(store.read_run("private-run"))

    message = str(captured.value)
    assert captured.value.error_type == "invalid_event"
    assert message.startswith("ledger:")
    assert "line 1" in message
    assert str(tmp_path) not in message
    assert secret not in message
    assert captured.value.__cause__ is None


def test_missing_run_lookups_do_not_grow_per_run_lock_state_without_bound(tmp_path):
    store = JsonlEventStore(tmp_path)

    for index in range(1_000):
        assert store.get_manifest(f"missing-{index}") is None

    assert len(store._run_locks) <= 64
    assert store._run_ids_by_directory == {}


def test_manifest_repair_write_is_best_effort_for_a_readable_ledger(tmp_path, monkeypatch):
    store = JsonlEventStore(tmp_path)
    store.append(event("readonly-cache", "event-0", "run.started"))
    manifest_path = next(tmp_path.glob("*/manifest.json"))
    manifest_path.write_text("{broken", encoding="utf-8")
    restarted = JsonlEventStore(tmp_path)

    def fail_write(_path, _data):
        raise OSError("read-only cache")

    monkeypatch.setattr(restarted, "_write_manifest", fail_write)

    manifest = restarted.get_manifest("readonly-cache")

    assert manifest["event_count"] == 1
    assert manifest["run_status"] == "running"


def test_orphan_zero_event_manifest_cannot_pollute_the_real_first_event(tmp_path):
    store = JsonlEventStore(tmp_path)
    run_id = "orphan-manifest"
    run_dir = store._run_dir(run_id)
    run_dir.mkdir()
    (run_dir / "manifest.json").write_text(
        json.dumps(
            {
                "run_id": run_id,
                "schema_version": "0.1.0",
                "created_at": "2020-01-01T00:00:00+00:00",
                "updated_at": "2020-01-01T00:00:00+00:00",
                "event_count": 0,
                "title": "Never persisted",
                "source_adapter": "orphan",
                "run_status": "unknown",
                "last_event_type": None,
                "last_event_hash": None,
            }
        ),
        encoding="utf-8",
    )

    store.append(
        event(
            run_id,
            "real-start",
            "run.started",
            payload={"title": "Authoritative title"},
        )
    )

    manifest = store.get_manifest(run_id)
    assert manifest["title"] == "Authoritative title"
    assert manifest["source_adapter"] == "tests"
    assert manifest["created_at"] != "2020-01-01T00:00:00+00:00"


def test_invalid_manifest_times_are_rebuilt_from_store_observation_times(tmp_path):
    store = JsonlEventStore(tmp_path)
    stored = store.append(event("invalid-times", "event-0", "run.started"))
    manifest_path = next(tmp_path.glob("*/manifest.json"))
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["created_at"] = "garbage"
    manifest["updated_at"] = "2026-07-17T10:00:00"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    rebuilt = JsonlEventStore(tmp_path).get_manifest("invalid-times")

    expected = stored.clock.observed_at.isoformat()
    assert rebuilt["created_at"] == expected
    assert rebuilt["updated_at"] == expected
