from __future__ import annotations

from dataclasses import dataclass
from threading import Lock


@dataclass(frozen=True)
class _LabelHandle:
    metric: CounterMetric
    labels: tuple[str, ...]

    def inc(self, amount: float = 1.0) -> None:
        self.metric._inc(self.labels, amount)


class CounterMetric:
    def __init__(self, name: str, help_text: str, labelnames: tuple[str, ...]) -> None:
        self.name = name
        self.help_text = help_text
        self.labelnames = labelnames
        self._values: dict[tuple[str, ...], float] = {}
        self._lock = Lock()

    def labels(self, **labels: str) -> _LabelHandle:
        values = tuple(labels.get(key, "") for key in self.labelnames)
        return _LabelHandle(metric=self, labels=values)

    def _inc(self, labels: tuple[str, ...], amount: float) -> None:
        with self._lock:
            self._values[labels] = self._values.get(labels, 0.0) + amount

    def render(self) -> list[str]:
        lines = [
            f"# HELP {self.name} {self.help_text}",
            f"# TYPE {self.name} counter",
        ]
        with self._lock:
            for labels, value in self._values.items():
                if self.labelnames:
                    label_expr = ",".join(
                        f'{key}="{CounterMetric._escape_label(val)}"'
                        for key, val in zip(self.labelnames, labels, strict=True)
                    )
                    lines.append(f"{self.name}{{{label_expr}}} {value}")
                else:
                    lines.append(f"{self.name} {value}")
        return lines

    @staticmethod
    def _escape_label(value: str) -> str:
        return value.replace("\\", "\\\\").replace("\"", "\\\"").replace("\n", "\\n")


TICKS_INGESTED_TOTAL = CounterMetric(
    name="ticks_ingested_total",
    help_text="Total number of ticks ingested by source and symbol.",
    labelnames=("source", "symbol"),
)

TICK_PUBLISH_FAILURES_TOTAL = CounterMetric(
    name="tick_publish_failures_total",
    help_text="Total number of tick publish failures by source.",
    labelnames=("source",),
)

METRICS_CONTENT_TYPE = "text/plain; version=0.0.4; charset=utf-8"


def render_metrics() -> bytes:
    lines: list[str] = []
    lines.extend(TICKS_INGESTED_TOTAL.render())
    lines.extend(TICK_PUBLISH_FAILURES_TOTAL.render())
    return ("\n".join(lines) + "\n").encode("utf-8")
