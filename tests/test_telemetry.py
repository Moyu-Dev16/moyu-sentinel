import pytest
import time
from src.telemetry import TelemetryCache

def test_telemetry_cache_hit():
    cache = TelemetryCache(offline_mode=True, cache_ttl=10.0)
    slot1, hash1 = cache.get_latest_slot_and_blockhash()
    slot2, hash2 = cache.get_latest_slot_and_blockhash()

    assert slot1 == slot2
    assert hash1 == hash2
    assert cache._cache_hits == 1
    assert cache._total_queries == 2

def test_slot_drift_detection_healthy():
    cache = TelemetryCache(offline_mode=True)
    current_slot, _ = cache.get_latest_slot_and_blockhash()

    # Slot lagging by only 10 slots
    valid, drift, msg = cache.check_slot_drift(current_slot - 10)
    assert valid is True
    assert drift == 10
    assert "Healthy" in msg

def test_slot_drift_detection_stale_lag():
    cache = TelemetryCache(offline_mode=True)
    current_slot, _ = cache.get_latest_slot_and_blockhash()

    # Slot lagging by 151 slots (> 150 limit)
    valid, drift, msg = cache.check_slot_drift(current_slot - 151)
    assert valid is False
    assert drift == 151
    assert "Stale blockhash / slot drift detected" in msg

def test_slot_drift_detection_future_anomaly():
    cache = TelemetryCache(offline_mode=True)
    current_slot, _ = cache.get_latest_slot_and_blockhash()

    # Future slot (e.g. current + 50)
    valid, drift, msg = cache.check_slot_drift(current_slot + 50)
    assert valid is False
    assert drift == -50
    assert "Future slot anomaly" in msg

def test_telemetry_snapshot():
    cache = TelemetryCache(offline_mode=True)
    snap = cache.get_snapshot()
    assert snap.current_slot > 0
    assert len(snap.latest_blockhash) > 0
    assert snap.status == "HEALTHY"
