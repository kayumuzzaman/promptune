"""Ollama model prewarm module.

Keeps a local Ollama model loaded in memory by periodically sending a
no-op generate request with a keep_alive parameter, avoiding cold-start
latency on the first real prompt.
"""

from __future__ import annotations

import logging
import threading

import httpx

logger = logging.getLogger(__name__)


def prewarm_ollama(
    host: str,
    model: str,
    keepalive: str = "30m",
) -> None:
    """Send a keep-alive ping to Ollama to keep the model loaded.

    Posts to ``{host}/api/generate`` with an empty prompt and the
    given ``keep_alive`` value.  All exceptions are caught and logged
    so this function never raises.

    Args:
        host: Base URL of the Ollama server, e.g. ``"http://localhost:11434"``.
        model: Name of the Ollama model to keep warm.
        keepalive: Ollama keep_alive duration string, e.g. ``"30m"``.
    """
    url = f"{host.rstrip('/')}/api/generate"
    payload = {"model": model, "prompt": "", "keep_alive": keepalive}
    try:
        response = httpx.post(url, json=payload, timeout=10.0)
        response.raise_for_status()
        logger.debug(
            "prewarm_ollama: model=%s host=%s status=%s",
            model,
            host,
            response.status_code,
        )
    except httpx.HTTPStatusError as exc:
        logger.warning(
            "prewarm_ollama: HTTP error for model=%s host=%s: %s",
            model,
            host,
            exc,
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "prewarm_ollama: connection error for model=%s host=%s: %s",
            model,
            host,
            exc,
        )


class _RepeatingTimer(threading.Timer):
    """A repeating timer: fires immediately, then once per ``interval``.

    Runs a single daemon thread that fires the function and then waits
    ``interval`` between fires (honoring the interval rather than busy-
    respawning). ``cancel()`` sets a stop event that ends the loop,
    interrupting an in-progress wait.
    """

    daemon = True

    def __init__(
        self,
        interval: float,
        function: object,
        args: object = None,
        kwargs: object = None,
        *,
        _stop_event: threading.Event | None = None,
    ) -> None:
        super().__init__(interval, function, args, kwargs)  # type: ignore[arg-type]
        self._stop_event = _stop_event or threading.Event()

    def cancel(self) -> None:  # type: ignore[override]
        """Cancel the timer and stop the repeating loop."""
        self._stop_event.set()
        super().cancel()

    def run(self) -> None:  # type: ignore[override]
        """Fire immediately, then re-fire every ``interval`` until stopped."""
        while not self._stop_event.is_set():
            self.function(*self.args, **self.kwargs)
            if self._stop_event.wait(self.interval):
                break


def start_prewarm_timer(
    host: str,
    model: str,
    interval_minutes: float = 25,
    keepalive: str = "30m",
) -> _RepeatingTimer:
    """Start a background timer that calls :func:`prewarm_ollama` periodically.

    Args:
        host: Ollama server base URL.
        model: Ollama model name.
        interval_minutes: How often to prewarm, in minutes.  Pass ``0``
            (or a very small value) during tests to trigger almost
            immediately — internally floored to ``0.01`` seconds when the
            computed interval would be zero.

    Returns:
        The first :class:`_RepeatingTimer` instance.  Keep a reference
        and call ``.cancel()`` to stop (cancels the current pending fire;
        see note in :class:`_RepeatingTimer`).
    """
    interval_seconds = interval_minutes * 60.0
    # Floor to a tiny positive value so tests with interval_minutes=0
    # still fire quickly rather than spinning at zero delay.
    if interval_seconds <= 0:
        interval_seconds = 0.01

    timer = _RepeatingTimer(
        interval_seconds,
        prewarm_ollama,
        args=(host, model, keepalive),
    )
    timer.daemon = True
    timer.start()
    return timer
