"""Small bounded timing records for local media jobs."""

import json
import time
from pathlib import Path


class MediaDiagnostics:
    """Collect stage timings without coupling media work to SQLite."""

    VERSION = 1
    MAX_SLOW_PARTS = 5
    PERSIST_PARTS = 32
    PERSIST_SECONDS = 2.0

    def __init__(
        self,
        on_change=lambda snapshot: None,
        clock=time.perf_counter,
        is_cancelled=lambda exc: False,
    ):
        self.on_change = on_change
        self.clock = clock
        self.is_cancelled = is_cancelled
        self.stages = {}
        self.parts = None
        self.last_part_persist = clock()

    @staticmethod
    def _seconds(value):
        return round(max(0.0, value), 4)

    def snapshot(self):
        result = {"version": self.VERSION, "stages": self.stages.copy()}
        if self.parts is not None:
            result["render_parts"] = self.parts.copy()
        # The schema has fixed fields and retains only five part samples.
        # This assertion protects future additions from silently growing jobs.
        if len(json.dumps(result, separators=(",", ":"))) > 8192:
            raise ValueError("Media diagnostics exceeded their storage bound")
        return json.loads(json.dumps(result))

    def _changed(self):
        self.on_change(self.snapshot())

    def measure(self, name, operation, output_path):
        self.stages[name] = {"status": "running"}
        self._changed()
        started = self.clock()
        try:
            result = operation()
        except Exception as exc:
            record = {
                "status": "cancelled" if self.is_cancelled(exc) else "failed",
                "elapsed_seconds": self._seconds(self.clock() - started),
                "error_type": type(exc).__name__,
            }
            self.stages[name] = record
            self._changed()
            raise
        record = {
            "status": "complete",
            "elapsed_seconds": self._seconds(self.clock() - started),
        }
        try:
            record["output_bytes"] = Path(output_path).stat().st_size
        except OSError:
            record["output_bytes"] = None
        self.stages[name] = record
        self._changed()
        return result

    def _begin_parts(self):
        if self.parts is None:
            self.parts = {
                "status": "running",
                "attempted_parts": 0,
                "completed_parts": 0,
                "elapsed_seconds": 0.0,
                "output_bytes": 0,
                "max_part_seconds": 0.0,
                "slowest_parts": [],
                "failed_part": None,
            }
            self._changed()

    def _persist_parts_if_due(self, force=False):
        now = self.clock()
        count = self.parts["attempted_parts"]
        if (
            force
            or count % self.PERSIST_PARTS == 0
            or now - self.last_part_persist >= self.PERSIST_SECONDS
        ):
            self.last_part_persist = now
            self._changed()

    def render_part(self, index, operation, output_path):
        self._begin_parts()
        started = self.clock()
        try:
            result = operation()
        except Exception as exc:
            elapsed = self._seconds(self.clock() - started)
            self.parts["attempted_parts"] += 1
            self.parts["elapsed_seconds"] = self._seconds(
                self.parts["elapsed_seconds"] + elapsed
            )
            self.parts["status"] = "cancelled" if self.is_cancelled(exc) else "failed"
            self.parts["failed_part"] = index
            self.parts["failed_part_seconds"] = elapsed
            self._persist_parts_if_due(force=True)
            raise

        elapsed = self._seconds(self.clock() - started)
        try:
            size = Path(output_path).stat().st_size
        except OSError:
            size = None
        self.parts["attempted_parts"] += 1
        self.parts["completed_parts"] += 1
        self.parts["elapsed_seconds"] = self._seconds(
            self.parts["elapsed_seconds"] + elapsed
        )
        if size is not None:
            self.parts["output_bytes"] += size
        self.parts["max_part_seconds"] = max(self.parts["max_part_seconds"], elapsed)
        sample = {"index": index, "elapsed_seconds": elapsed, "output_bytes": size}
        self.parts["slowest_parts"] = sorted(
            [*self.parts["slowest_parts"], sample],
            key=lambda part: (-part["elapsed_seconds"], part["index"]),
        )[: self.MAX_SLOW_PARTS]
        self._persist_parts_if_due()
        return result

    def finish_parts(self):
        if self.parts is not None:
            self.parts["status"] = "complete"
            self._changed()
