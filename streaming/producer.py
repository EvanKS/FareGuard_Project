"""
FareGuard Synthetic Event Stream Producer

Publishes continuous transit ticketing and operational events to the stream manager.
Supports configurable event rates, simulation speeds, batch publishing, and deterministic testing.
"""

import logging
import time
from typing import Any, Dict, List, Optional
import pandas as pd

from streaming.event_schema import TransitEvent
from streaming.stream_manager import StreamManager

logger = logging.getLogger(__name__)


class EventProducer:
    """
    Simulates operational transit telemetry stream publishing.
    """

    def __init__(
        self,
        stream_manager: StreamManager,
        rate_events_per_sec: float = 50.0,
        batch_size: int = 10,
    ):
        self.stream_manager = stream_manager
        self.rate_events_per_sec = max(0.1, rate_events_per_sec)
        self.batch_size = max(1, batch_size)
        self._is_active = False
        self.total_published = 0

    def publish_single_event(self, event: TransitEvent) -> str:
        """Publishes a single validated TransitEvent."""
        errors = event.validate()
        if errors:
            raise ValueError(f"Cannot publish invalid TransitEvent: {errors}")

        msg_id = self.stream_manager.publish(event.to_dict())
        self.total_published += 1
        return msg_id

    def publish_events_batch(self, events: List[TransitEvent]) -> List[str]:
        """Publishes a batch of TransitEvents."""
        msg_ids = []
        for evt in events:
            msg_ids.append(self.publish_single_event(evt))
        return msg_ids

    def stream_from_dataframe(
        self,
        df: pd.DataFrame,
        max_events: Optional[int] = None,
        delay_between_batches: float = 0.01,
    ) -> int:
        """
        Streams events from a pandas DataFrame at a controlled pacing.
        """
        self._is_active = True
        count = 0
        limit = max_events if max_events is not None else len(df)

        for _, row in df.iloc[:limit].iterrows():
            if not self._is_active:
                break

            evt = TransitEvent(
                event_id=str(row.get("event_id", f"EVT-{count + 1}")),
                timestamp=str(row.get("timestamp", pd.Timestamp.now().isoformat())),
                route_id=str(row.get("route_id", "335-E")),
                trip_id=str(row.get("trip_id", f"TRIP-{count + 1}")),
                bus_id=str(row.get("bus_id", "KA-01-F-1234")),
                from_stop=str(row.get("from_stop", "Stop_A")),
                to_stop=str(row.get("to_stop", "Stop_B")),
                passenger_count=int(row.get("passenger_count", row.get("total_passengers", 40))),
                fare=float(row.get("fare", 12.03)),
                revenue=float(row.get("revenue", row.get("total_revenue_inr", 480.0))),
                payment_mode=str(row.get("payment_mode", "CASH")),
                synthetic_flag=bool(row.get("synthetic_flag", True)),
                sequence_number=int(row.get("sequence_number", 1)),
            )

            self.publish_single_event(evt)
            count += 1

            if count % self.batch_size == 0 and delay_between_batches > 0:
                time.sleep(delay_between_batches)

        self._is_active = False
        return count

    def stop(self):
        """Halts active streaming loop."""
        self._is_active = False


# Backward compatibility alias
StreamProducer = EventProducer
