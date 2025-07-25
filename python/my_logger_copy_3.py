import logging
import logging.handlers
import multiprocessing
import time
from pathlib import Path

def configure_listener_handler(logfile: Path):
    formatter = logging.Formatter(
        fmt="%(asctime)s.%(msecs)03d - %(levelname)s - %(processName)s - %(module)s.%(funcName)s:%(lineno)d - %(message)s",
        datefmt="%d-%m-%Y %H:%M:%S",
    )
    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(formatter)
    file_handler = logging.FileHandler(logfile, encoding="utf-8")
    file_handler.setFormatter(formatter)
    return [stream_handler, file_handler]

def logger_process(log_queue, logfile: Path):
    handlers = configure_listener_handler(logfile)
    listener = logging.handlers.QueueListener(log_queue, *handlers)
    listener.start()
    while True:
        time.sleep(0.1)  # Listener läuft, bis Prozess beendet wird

def worker_process(log_queue, n):
    # Jeder Worker bekommt einen QueueHandler, der auf die gemeinsame Queue schreibt
    queue_handler = logging.handlers.QueueHandler(log_queue)
    logger = logging.getLogger(f"worker-{n}")
    logger.setLevel(logging.DEBUG)
    logger.addHandler(queue_handler)
    logger.propagate = False

    for i in range(5):
        logger.info(f"Prozess {n} meldet: {i}")
        time.sleep(0.1)

if __name__ == "__main__":
    log_queue = multiprocessing.Queue(-1)
    logfile = Path("multiproc_log.txt")
    
    process_logger = multiprocessing.Process(target=logger_process, args=(log_queue, logfile), daemon=True)
    process_logger.start()

    processes = [multiprocessing.Process(target=worker_process, args=(log_queue, i)) for i in range(3)]
    for p in processes:
        p.start()
    for p in processes:
        p.join()

    # Listener beenden (hier: einfach Prozess killen, sauberer wäre ein Stop-Event)
    process_logger.terminate()
    process_logger.join()
