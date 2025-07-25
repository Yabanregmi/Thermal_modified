from typing import List
import logging
import logging.handlers
import queue
from pathlib import Path


class MyLogger(logging.Logger):
    """
    Multiprozess-fähiger Logger auf Basis von logging.Logger mit zentralem QueueListener.
    Jeder MyLogger schreibt in eine gemeinsame Queue, die von einem Listener-Prozess
    abgearbeitet und in Datei und/oder Konsole geschrieben wird.
    """

    # Klassenattribute: gemeinsame Queue für alle Logger und ein gemeinsamer Listener
    _instances: int = 0  # Anzahl der aktiven Logger-Instanzen
    _log_queue: queue.Queue[str] = queue.Queue(
        maxsize=100)  # Nachrichten-Queue
    _log_listener = None  # Der zentrale QueueListener

    # Standard Logdatei (relativ zum Skript)
    _sLog_file: Path
    _xEnable_stream_handler = True  # Soll auch auf die Konsole geloggt werden?

    def __init__(
        self,
        name: str,
        sLevel: str = "DEBUG",
        sFilePath: Path = Path(__file__).parent / "log.txt",
    ):
        """
        Initialisiert eine neue Logger-Instanz.
        :param name: Name des Loggers (z.B. Modulname)
        :param sLevel: Loglevel als String ("DEBUG", "INFO", ...)
        :param sFilePath: Pfad zur Logdatei
        """
        MyLogger._instances += 1
        levels = {
            "DEBUG": logging.DEBUG,
            "INFO": logging.INFO,
            "WARNING": logging.WARNING,
            "ERROR": logging.ERROR,
            "CRITICAL": logging.CRITICAL,
        }
        self._sLog_file = sFilePath

        if sLevel not in levels:
            raise ValueError(f"Invalid logging level: {sLevel}")
        level = levels[sLevel]

        # Basisklasse initialisieren
        logging.Logger.__init__(self, name=name)
        self.setLevel(level)

        # Alte Handler entfernen, falls Logger wiederverwendet wird
        if self.hasHandlers():
            self.handlers.clear()

        # Format für Logeinträge definieren
        formatter = logging.Formatter(
            fmt="%(asctime)s.%(msecs)03d - %(levelname)s - %(threadName)s - %(module)s.%(funcName)s:%(lineno)d - %(message)s",
            datefmt="%d-%m-%Y %H:%M:%S",
        )

        # Liste der Handler für den Listener
        handlers: List[logging.Handler] = []

        # FileHandler für Logdatei hinzufügen, falls gewünscht
        if self._sLog_file:
            self._sLog_file.parent.mkdir(parents=True, exist_ok=True)
            fh = logging.FileHandler(self._sLog_file, encoding="utf-8")
            fh.setLevel(level)
            fh.setFormatter(formatter)
            handlers.append(fh)

        # Optional: StreamHandler für die Konsole
        if self._xEnable_stream_handler:
            sh = logging.StreamHandler()
            sh.setLevel(level)
            sh.setFormatter(formatter)
            handlers.append(sh)

        # QueueHandler – alle Logeinträge gehen in die gemeinsame Queue
        queue_handler = logging.handlers.QueueHandler(self._log_queue)
        queue_handler.setLevel(level)
        self.addHandler(queue_handler)

        # Listener wird nur einmal pro Programmstart initialisiert
        self._start_listener_once(*handlers)

    def __del__(self):
        """
        Verringert den Zähler der Logger-Instanzen beim Löschen.
        """
        MyLogger._instances -= 1

    @classmethod
    def _start_listener_once(cls, *handlers: logging.Handler):
        """
        Startet den zentralen QueueListener, falls noch nicht vorhanden.
        Der Listener schreibt die Logeinträge aus der Queue in die Handler (Datei/Konsole).
        """
        if cls._log_listener is None:
            cls._log_listener = logging.handlers.QueueListener(
                cls._log_queue, *handlers
            )
            cls._log_listener.start()

    def stop_instance(self):
        """
        Schließt alle Handler dieser Logger-Instanz (z.B. QueueHandler).
        Sollte aufgerufen werden, wenn die Instanz nicht mehr gebraucht wird.
        """
        for handler in self.handlers[:]:
            handler.flush()
            handler.close()
            self.removeHandler(handler)

    @classmethod
    def stopAll(cls):
        """
        Stoppt den zentralen QueueListener und schließt alle Handler.
        Sollte beim Programmende aufgerufen werden, um alle Ressourcen freizugeben.
        """
        if cls._log_listener:
            cls._log_listener.stop()
            cls._log_listener = None

        # Handler des Root-Loggers schließen (optional)
        root_logger = logging.getLogger()
        for handler in root_logger.handlers[:]:
            handler.flush()
            handler.close()
            root_logger.removeHandler(handler)

        logging.shutdown()

    @classmethod
    def get_instance_count(cls):
        """
        Gibt die aktuelle Anzahl der MyLogger-Instanzen zurück.
        :return: Instanzzähler (int)
        """
        return cls._instances

import multiprocessing
import time
from pathlib import Path

# (Hier kommt die Klasse MyLogger wie oben...)

def worker_proc(name: str):
    """
    Ein Worker-Prozess, der ein paar Logeinträge schreibt.
    """
    logger = MyLogger(name, sLevel="INFO", sFilePath=Path("log.txt"))
    for i in range(3):
        logger.info(f"[{name}] Schritt {i+1}")
        time.sleep(0.5)
    logger.info(f"[{name}] Fertig.")

def main():
    logger = MyLogger("main", sLevel="DEBUG", sFilePath=Path("log.txt"))
    logger.info("Starte Multiprozess-Logging-Demo")

    procs = []
    for i in range(2):
        p = multiprocessing.Process(target=worker_proc, args=(f"worker-{i+1}",))
        procs.append(p)
        p.start()
        logger.info(f"Worker-{i+1} gestartet.")

    for p in procs:
        p.join()
        logger.info(f"{p.name} beendet.")

    logger.info("Alle Worker fertig, Logging wird gestoppt.")
    MyLogger.stopAll()

if __name__ == "__main__":
    main()

