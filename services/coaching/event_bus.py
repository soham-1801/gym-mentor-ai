import queue
import logging
import time

class VoiceEventBus:
    def __init__(self):
        self.queue = queue.Queue()
        self.published_count = 0
        self.consumed_count = 0
        logging.info("[VoiceEventBus] Initialized VoiceEventBus.")

    def publish(self, event_type, payload=None):
        """Publish an event to the bus from any thread."""
        self.queue.put((event_type, payload or {}))
        self.published_count += 1
        logging.info(f"[VoiceEventBus] [PUBLISH] Event='{event_type}', Payload={payload} (Total published: {self.published_count})")

    def consume_all(self):
        """Consume and return all currently pending events in the queue (thread-safe drain)."""
        events = []
        while True:
            try:
                event = self.queue.get_nowait()
                events.append(event)
                self.consumed_count += 1
                logging.debug(f"[VoiceEventBus] [CONSUME] Event='{event[0]}' (Total consumed: {self.consumed_count})")
            except queue.Empty:
                break
        return events
