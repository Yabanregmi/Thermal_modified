import time
from dataclasses import dataclass

@dataclass
class QueueMessage:
    command : str = ""
    timestamp: float = time.time()
    data : str = ""

    def __post_init__(self):

        # Aktuelle Zeit, falls nicht gesetzt
        if not self.timestamp:
            self.timestamp = time.time()
