"""
FareGuard Streaming Engine and Queue Manager

Provides unified streaming abstraction supporting Redis Streams with an automatic,
robust in-memory fallback for environments where Redis server is not running.
"""

import json
import logging
import queue
import time
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# Attempt to import redis safely
try:
    import redis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False


class StreamManager:
    """
    Manages publish/subscribe operations across Redis Streams or local in-memory queue.
    """

    def __init__(
        self,
        stream_name: str = "fareguard:events",
        consumer_group: str = "fareguard_cg",
        redis_host: str = "localhost",
        redis_port: int = 6379,
        redis_db: int = 0,
        use_fallback: bool = True,
    ):
        self.stream_name = stream_name
        self.consumer_group = consumer_group
        self.redis_host = redis_host
        self.redis_port = redis_port
        self.redis_db = redis_db
        self.use_fallback = use_fallback

        self.redis_client: Optional[Any] = None
        self.is_redis_connected = False
        self._local_queue: queue.Queue = queue.Queue()
        self._dlq_queue: queue.Queue = queue.Queue()
        self._is_running = True

        self._initialize_connection()

    def _initialize_connection(self):
        """Attempts connection to Redis, falling back to in-memory queue if unavailable."""
        if REDIS_AVAILABLE:
            try:
                client = redis.Redis(
                    host=self.redis_host,
                    port=self.redis_port,
                    db=self.redis_db,
                    socket_connect_timeout=1.0,
                    socket_timeout=1.0,
                    decode_responses=True,
                )
                client.ping()
                self.redis_client = client
                self.is_redis_connected = True
                logger.info(f"Connected to Redis at {self.redis_host}:{self.redis_port}")
                # Create consumer group if not exists
                try:
                    self.redis_client.xgroup_create(self.stream_name, self.consumer_group, id="0", mkstream=True)
                except redis.ResponseError as e:
                    if "BUSYGROUP" not in str(e):
                        logger.warning(f"Consumer group error: {e}")
                return
            except Exception as e:
                logger.warning(f"Redis connection failed ({e}). Using robust In-Memory Stream Queue.")
                self.redis_client = None
                self.is_redis_connected = False
        else:
            logger.info("redis-py not installed or unavailable. Using robust In-Memory Stream Queue.")
            self.redis_client = None
            self.is_redis_connected = False

    def publish(self, event_data: Dict[str, Any]) -> str:
        """Publishes an event dictionary to the active stream."""
        if not self._is_running:
            raise RuntimeError("StreamManager is stopped.")

        payload_str = json.dumps(event_data)

        if self.is_redis_connected and self.redis_client:
            try:
                msg_id = self.redis_client.xadd(self.stream_name, {"payload": payload_str})
                return str(msg_id)
            except Exception as e:
                logger.warning(f"Redis publish failed ({e}). Falling back to local queue.")
                self.is_redis_connected = False

        # In-memory queue fallback
        msg_id = f"mem-{time.time_ns()}"
        self._local_queue.put((msg_id, event_data))
        return msg_id

    def read_events(self, consumer_name: str = "worker-1", count: int = 10, block_ms: int = 100) -> List[Tuple[str, Dict[str, Any]]]:
        """Reads a batch of events from the stream."""
        if not self._is_running:
            return []

        events: List[Tuple[str, Dict[str, Any]]] = []

        if self.is_redis_connected and self.redis_client:
            try:
                res = self.redis_client.xreadgroup(
                    groupname=self.consumer_group,
                    consumername=consumer_name,
                    streams={self.stream_name: ">"},
                    count=count,
                    block=block_ms,
                )
                if res:
                    for stream, messages in res:
                        for msg_id, fields in messages:
                            payload_str = fields.get("payload", "{}")
                            events.append((str(msg_id), json.loads(payload_str)))
                return events
            except Exception as e:
                logger.warning(f"Redis read failed ({e}). Using local queue.")
                self.is_redis_connected = False

        # Local in-memory read
        for _ in range(count):
            try:
                msg_id, data = self._local_queue.get(block=True, timeout=block_ms / 1000.0)
                events.append((msg_id, data))
                self._local_queue.task_done()
            except queue.Empty:
                break
        return events

    def ack(self, msg_id: str):
        """Acknowledges successful event processing."""
        if self.is_redis_connected and self.redis_client and not msg_id.startswith("mem-"):
            try:
                self.redis_client.xack(self.stream_name, self.consumer_group, msg_id)
            except Exception as e:
                logger.warning(f"Redis ACK failed ({e})")

    def dead_letter(self, msg_id: str, event_data: Dict[str, Any], reason: str):
        """Sends malformed or unprocessable events to Dead-Letter Queue."""
        dlq_entry = {"msg_id": msg_id, "data": event_data, "reason": reason, "timestamp": time.time()}
        self._dlq_queue.put(dlq_entry)
        logger.warning(f"Dead-lettered message {msg_id}: {reason}")

    def get_dlq_count(self) -> int:
        """Returns number of events currently in Dead-Letter Queue."""
        return self._dlq_queue.qsize()

    def get_health_status(self) -> Dict[str, Any]:
        """Returns stream engine health metrics."""
        return {
            "is_running": self._is_running,
            "engine": "Redis Streams" if self.is_redis_connected else "In-Memory Stream Queue",
            "redis_connected": self.is_redis_connected,
            "local_queue_size": self._local_queue.qsize(),
            "dlq_size": self._dlq_queue.qsize(),
            "stream_name": self.stream_name,
        }

    def clear(self):
        """Clears local queues."""
        while not self._local_queue.empty():
            try:
                self._local_queue.get_nowait()
            except queue.Empty:
                break
        while not self._dlq_queue.empty():
            try:
                self._dlq_queue.get_nowait()
            except queue.Empty:
                break

    def stop(self):
        """Gracefully shuts down stream manager."""
        self._is_running = False
