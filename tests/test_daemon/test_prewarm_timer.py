"""Linux-runnable tests for the _RepeatingTimer interval behavior.

These exercise only the pure-threading timer (no macOS APIs), so unlike
test_prewarm.py they are not platform-gated.
"""

from __future__ import annotations

import threading
import time

from promptune.daemon.prewarm import _RepeatingTimer


def test_repeating_timer_honors_interval_not_busy_loop() -> None:
    """The timer waits ~interval between fires instead of respawning at full speed."""
    count = 0

    def _tick() -> None:
        nonlocal count
        count += 1

    timer = _RepeatingTimer(0.02, _tick)
    timer.start()
    try:
        time.sleep(0.12)
    finally:
        timer.cancel()
    # Fires immediately then every ~0.02s: expect a handful, never hundreds.
    assert 2 <= count <= 30


def test_repeating_timer_cancel_stops_loop() -> None:
    """cancel() ends the loop and interrupts the pending interval wait."""
    count = 0

    def _tick() -> None:
        nonlocal count
        count += 1

    timer = _RepeatingTimer(0.02, _tick)
    timer.start()
    time.sleep(0.05)
    timer.cancel()
    settled = count
    time.sleep(0.1)
    assert count == settled


def test_repeating_timer_shared_stop_event() -> None:
    """A pre-set shared stop event prevents any fire."""
    event = threading.Event()
    event.set()
    count = 0

    def _tick() -> None:
        nonlocal count
        count += 1

    timer = _RepeatingTimer(0.01, _tick, _stop_event=event)
    timer.start()
    time.sleep(0.05)
    timer.cancel()
    assert count == 0
