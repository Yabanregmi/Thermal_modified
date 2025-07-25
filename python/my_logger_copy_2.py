import logging
import logging.handlers
import queue
import threading
from typing import List
from pathlib import Path

class ThreadedLogger:
    def __init__(
        self,
        name: str,
        loglevel=logging.INFO,
        sFilePath: Path = Path(__file__).parent / "log.txt",
    ):
        self.sFilePath: Path = sFilePath
        self.log_queue = queue.Queue(maxsize=100)
        
        self.logger = logging.getLogger(name)
        self.logger.setLevel(loglevel)
        self.logger.propagate = False
        
        self.formatter = logging.Formatter(
            fmt="%(asctime)s.%(msecs)03d - %(levelname)s - %(threadName)s - %(module)s.%(funcName)s:%(lineno)d - %(message)s",
            datefmt="%d-%m-%Y %H:%M:%S",
        )
        self.queue_handler = logging.handlers.QueueHandler(self.log_queue)
        self.logger.addHandler(self.queue_handler)

        # Zielhandler: Konsole
        self.stream_handler = logging.StreamHandler()
        self.stream_handler.setFormatter(self.formatter)

        # Zielhandler: Datei
        self.sFilePath.parent.mkdir(parents=True, exist_ok=True)
        self.file_handler = logging.FileHandler(self.sFilePath, encoding="utf-8")
        self.file_handler.setFormatter(self.formatter)

        # Handler an logger übergeben
        self.listener = logging.handlers.QueueListener(
            self.log_queue, self.stream_handler, self.file_handler
        )
        self.listener.start()

    def get_logger(self):
        return self.logger

    def stop(self):
        self.listener.stop()
        self.logger.removeHandler(self.queue_handler)
        self.stream_handler.close()
        self.file_handler.close()


# Beispielnutzung:
if __name__ == "__main__":
    logsys = ThreadedLogger("myapp", logging.DEBUG)
    logger = logsys.get_logger()
    
    def worker(n):
        for i in range(3):
            logger.info(f"Thread {n} meldet: {i}")
            
    threads = [threading.Thread(target=worker, args=(i,)) for i in range(2)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    
    logsys.stop()
