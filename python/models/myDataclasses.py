import time
from dataclasses import dataclass


@dataclass
class QueueMessage:
    sender: str

    receiver: str
    command: str

    payload: int
    timestamp: float = time.time()

    def __post_init__(self):

        # Aktuelle Zeit, falls nicht gesetzt
        if not self.timestamp:
            self.timestamp = time.time()
