import logging
import logging.handlers
import multiprocessing
from pathlib import Path
import time

class GlobalMPLogger:
    log_queue : multiprocessing.Queue 
    listener_process : multiprocessing.Process 
    logfile : Path 
    loglevel = logging.INFO

    @classmethod
    def configure(cls, logfile: Path, loglevel=logging.INFO):
        cls.log_queue = multiprocessing.Queue(-1)
        cls.logfile = logfile
        cls.loglevel = loglevel
        cls.listener_process = multiprocessing.Process(
            target=cls._listener_process_target,
            args=(cls.log_queue, cls.logfile),
            daemon=True
        )

    @classmethod
    def _configure_handlers(cls, logfile):
        formatter = logging.Formatter(
            fmt="%(asctime)s.%(msecs)03d - %(levelname)s - %(processName)s - %(module)s.%(funcName)s:%(lineno)d - %(message)s",
            datefmt="%d-%m-%Y %H:%M:%S",
        )
        stream_handler = logging.StreamHandler()
        stream_handler.setFormatter(formatter)
        file_handler = logging.FileHandler(logfile, encoding="utf-8")
        file_handler.setFormatter(formatter)
        return [stream_handler, file_handler]

    @classmethod
    def _listener_process_target(cls, log_queue, logfile):
        handlers = cls._configure_handlers(logfile)
        listener = logging.handlers.QueueListener(log_queue, *handlers)
        listener.start()
        try:
            while True:
                time.sleep(0.1)
        except KeyboardInterrupt:
            pass
        finally:
            listener.stop()

    @classmethod
    def start(cls):
        if cls.listener_process:
            cls.listener_process.start()

    @classmethod
    def get_logger(cls, name):
        logger = logging.getLogger(name)
        logger.setLevel(cls.loglevel)
        logger.handlers = []
        logger.propagate = False
        logger.addHandler(logging.handlers.QueueHandler(cls.log_queue))
        return logger

    @classmethod
    def stop(cls):
        if cls.listener_process:
            cls.listener_process.terminate()
            cls.listener_process.join()

# if __name__ == "__main__":
#     GlobalMPLogger.configure(Path("log.txt"), logging.DEBUG)
#     GlobalMPLogger.start()

#     logger_main_process = GlobalMPLogger.get_logger("mainprozess")

#     logger_main_process.info("Thread meldet: TEST 1")
#     logger_main_process.error("Thread meldet: TEST 2")

#     # Wichtig: Gib dem Listener Zeit, die Queue zu verarbeiten!
#     time.sleep(1)

#     GlobalMPLogger.stop()