from typing import Dict, Optional, Tuple
import multiprocessing
from multiprocessing import Process, Queue, Event
import time
from myLogger import MyLogger
from models.myDataclasses import QueueMessage
import socketio
from ringbuffer import RingBuffer
from config import DB_PATH, SERVER_URL, MAX_ROWS, BUFFER_SIZE, SLEEP_TIME
import random
from datetime import datetime
from checksums import get_batch_checksum, get_crc

# Maximale Wartezeit für bestimmte Operationen (in Sekunden)
MAXIMUM_TIMEOUT: int = 10
# Maximale Größe der Queue (Anzahl Nachrichten)
QUEUE_MAXSIZE: int = 128


class MyEvent:
    """
    Wrapper-Klasse für multiprocessing.Event, um einen einheitlichen Umgang mit Events zu ermöglichen.
    Wird genutzt, um prozessübergreifende Signale (z.B. Heartbeat oder Shutdown) zu setzen und abzufragen.
    """

    def __init__(self):
        """Erzeugt ein neues multiprocessing.Event für die Synchronisation zwischen Prozessen."""
        self._event: Event = Event()

    def is_set(self) -> bool:
        """Gibt zurück, ob das Event aktuell gesetzt ist (True/False)."""
        return self._event.is_set()

    def set(self) -> None:
        """Setzt das Event (signalisiert allen wartenden Prozessen das Ereignis)."""
        self._event.set()

    def clear(self) -> None:
        """Löscht das Event (setzt es auf 'nicht gesetzt')."""
        self._event.clear()

    def wait(self, timeout=None) -> bool:
        """
        Blockiert, bis das Event gesetzt ist oder ein Timeout auftritt.
        :param timeout: Maximale Wartezeit in Sekunden (oder None für unendlich)
        :return: True, wenn das Event gesetzt wurde, sonst False (bei Timeout)
        """
        return self._event.wait(timeout)


class MyQueue:
    """
    Wrapper für multiprocessing.Queue mit fester Maximalgröße.
    Wird als Kommunikationskanal zum Nachrichtenaustausch zwischen Prozessen verwendet.
    """

    def __init__(self):
        """Initialisiert eine neue Queue mit fester Maximalgröße."""
        self._queue: Queue = Queue(maxsize=QUEUE_MAXSIZE)

    def put(self, item: QueueMessage, block: bool = False, timeout: Optional[float] = 0) -> None:
        """
        Legt ein Element in die Queue.
        :param item: Das zu speichernde Objekt
        :param block: Ob blockierend gewartet werden soll, falls die Queue voll ist
        :param timeout: Maximale Wartezeit in Sekunden
        """
        self._queue.put(item, block, timeout)

    def get(self, block: bool = False, timeout: Optional[float] = 0) -> QueueMessage:
        """
        Holt ein Element aus der Queue.
        :param block: Ob blockierend gewartet werden soll, falls die Queue leer ist
        :param timeout: Maximale Wartezeit in Sekunden
        :return: Das nächste Element aus der Queue
        """
        return self._queue.get(block, timeout)


class WriteOnlyQueue:
    """
    Queue-Wrapper, der ausschließlich das Schreiben (put) erlaubt.
    Lesezugriffe (get) führen zu einem Fehler.
    Wird genutzt, um die Richtung der Kommunikation explizit zu machen.
    """

    def __init__(self, queue: MyQueue):
        """Initialisiert die WriteOnlyQueue mit einer MyQueue."""
        self._queue: MyQueue = queue

    def put(self, item: QueueMessage, block: bool = False, timeout: Optional[float] = 0) -> None:
        """Fügt ein Element in die zugrundeliegende Queue ein."""
        return self._queue.put(item=item, block=block, timeout=timeout)

    def get(self, block: bool = False, timeout: Optional[float] = 0) -> QueueMessage:
        """Lesezugriffe sind nicht erlaubt und werfen einen Fehler."""
        raise RuntimeError("This queue is write-only!")


class ReadOnlyQueue:
    """
    Queue-Wrapper, der ausschließlich das Lesen (get) erlaubt.
    Schreibzugriffe (put) führen zu einem Fehler.
    Wird genutzt, um die Richtung der Kommunikation explizit zu machen.
    """

    def __init__(self, queue: MyQueue):
        """Initialisiert die ReadOnlyQueue mit einer MyQueue."""
        self._queue = queue

    def get(self, block: bool = False, timeout: Optional[float] = 0) -> QueueMessage:
        """Liest ein Element aus der zugrundeliegenden Queue."""
        return self._queue.get(block=block, timeout=timeout)

    def put(self, item: QueueMessage, block: bool = False, timeout: Optional[float] = 0) -> None:
        """Schreibzugriffe sind nicht erlaubt und werfen einen Fehler."""
        raise RuntimeError("This queue is read-only!")


class BaseProcess(Process):
    """
    Basisklasse für alle Prozesse im System.
    Stellt die gemeinsame Schnittstelle für Shutdown- und Heartbeat-Events bereit.
    """
    logger = MyLogger(__name__, sLevel="DEBUG")

    def __init__(self, name: str, event_shutdown: MyEvent, event_heartbeat: MyEvent):
        """
        :param name: Name des Prozesses (zur Identifikation und für Logging)
        :param event_shutdown: Event-Objekt für das Beenden des Prozesses
        :param event_heartbeat: Event-Objekt für Heartbeat-Signalisierung
        """
        super().__init__()
        self.name: str = name
        self.event_shutdown: MyEvent = event_shutdown
        self.event_heartbeat: MyEvent = event_heartbeat

    def send_hearbeat_event(self):
        """
        Setzt das Heartbeat-Event, falls es noch nicht gesetzt ist.
        Wird regelmäßig vom Kindprozess aufgerufen, um dem Hauptprozess zu signalisieren, dass der Prozess lebt.
        """
        if not self.event_heartbeat.is_set():
            self.event_heartbeat.set()


class ServerProcess(BaseProcess):
    """
    Beispielprozess für einen Server, der mit mehreren Queues kommuniziert
    und über ein Event sauber beendet werden kann.
    Sendet regelmäßig einen Heartbeat an den Hauptprozess.
    """
    sio = socketio.Client()
    in_konfig_modus = False
    server_connected = False
    buffer = RingBuffer(BUFFER_SIZE)

    def __init__(
        self,
        name: str,
        queue_server: MyQueue,
        queue_io: MyQueue,
        queue_db: MyQueue,
        event_shutdown: MyEvent,
        event_heartbeat: MyEvent
    ):
        """
        Initialisiert den Serverprozess mit den erforderlichen Queues und Events.
        """
        super().__init__(name=name, event_shutdown=event_shutdown,
                         event_heartbeat=event_heartbeat)
        # Server liest nur von queue_server, schreibt aber auf queue_io und queue_db
        self.queue_server: ReadOnlyQueue = ReadOnlyQueue(queue_server)
        self.queue_io: WriteOnlyQueue = WriteOnlyQueue(queue_io)
        self.queue_db: WriteOnlyQueue = WriteOnlyQueue(queue_db)

        # Beispiel-Nachrichten für die Kommunikation
        self.msgIr: QueueMessage = QueueMessage(
            sender="server", receiver="ir", command="Hello", payload=42
        )
        self.msgDb: QueueMessage = QueueMessage(
            sender="server", receiver="db", command="Hello", payload=42
        )
        self.rxMsg: QueueMessage  # Empfangene Nachricht (Platzhalter)

    def run(self):
        """
        Hauptschleife des Serverprozesses.
        Prüft regelmäßig das Shutdown-Event und sendet Heartbeats.
        """
        try:
            self.register_events()
            self.connect_to_server(SERVER_URL)

            while not self.event_shutdown.is_set():
                self.send_hearbeat_event()
                self.startTest()
                # Hier kann weitere Server-Logik implementiert werden
                time.sleep(0.01)  # Dummy-Loop, um CPU zu schonen
        except Exception as exc:
            self.logger.error(f"Exception {self.name}: {exc}")
        self.logger.debug(f"Close {self.name}")
        time.sleep(1)  # Kurze Pause vor Prozessende

    def startTest(self):
        wert = round(random.uniform(20.0, 25.0), 1)
        zeit = datetime.utcnow().isoformat()
        self.buffer.append((wert, zeit))

        # Live an den Server senden (mit CRC32-Prüfsumme)
        if self.is_server_connected():
            crc = get_crc(wert, zeit)
            self.send_live_temperatur(wert, zeit, crc)

        # Nur speichern, wenn NICHT im Konfigmodus!
        if not self.is_in_konfig_modus() and self.buffer.is_full():
            values = self.buffer.get_all()
            batch_checksum = get_batch_checksum(values)
            db_values = [(wert, zeit, batch_checksum)
                         for wert, zeit in values]
            self.logger.debug(
                "[DB] Keine Verbindung zur Datenbank; Batch zwischengespeichert.")

            self.buffer.clear()

        time.sleep(
            SLEEP_TIME if not self.is_in_konfig_modus() else 0.2)

    def register_events(self):
        @self.sio.event
        def connect():
            self.server_connected = True
            self.logger.debug("Verbunden mit Node.js-Server.")

        @self.sio.event
        def disconnect():
            self.server_connected = False
            self.logger.debug("Verbindung zum Node.js-Server getrennt.")

        @self.sio.on('konfigModusStart')
        def on_konfig_start():
            self.logger.debug("Konfigurationsmodus AKTIV")
            self.in_konfig_modus = True
            self.sio.emit("konfigReady")  # Rückmeldung an den Server

        @self.sio.on('konfigModusEnde')
        def on_konfig_ende():
            self.logger.debug("Konfigurationsmodus BEENDET")
            self.in_konfig_modus = False

    def connect_to_server(self, server_url):
        try:
            self.sio.connect(server_url)
        except Exception as e:
            self.logger.debug(f"[Server] Fehler bei Verbindung: {e}")

    def send_live_temperatur(self, wert, zeit, crc):
        try:
            self.sio.emit("liveTemperatur", {
                "wert": f"{wert:.1f}",
                "zeit": zeit,
                "crc": crc
            })
        except Exception as e:
            self.logger.debug(f"[Server] Fehler beim Senden: {e}")

    def is_in_konfig_modus(self) -> bool:
        return self.in_konfig_modus

    def is_server_connected(self) -> bool:
        return self.server_connected

    def disconnect(self):
        try:
            self.sio.disconnect()
        except Exception:
            pass


class IoProcess(BaseProcess):
    """
    Beispielprozess für IO-Aufgaben, der mit Queues und Event arbeitet.
    Sendet regelmäßig einen Heartbeat.
    """

    def __init__(
        self,
        name: str,
        queue_server: MyQueue,
        queue_io: MyQueue,
        queue_db: MyQueue,
        event_shutdown: MyEvent,
        event_heartbeat: MyEvent
    ):
        super().__init__(name=name, event_shutdown=event_shutdown,
                         event_heartbeat=event_heartbeat)
        # IO schreibt auf queue_server und queue_db, liest aber von queue_io
        self.queue_server: WriteOnlyQueue = WriteOnlyQueue(queue_server)
        self.queue_io: ReadOnlyQueue = ReadOnlyQueue(queue_io)
        self.queue_db: WriteOnlyQueue = WriteOnlyQueue(queue_db)
        self.shutdown_event = event_shutdown

    def run(self):
        """
        Hauptschleife des IO-Prozesses. Prüft regelmäßig das Shutdown-Event und sendet Heartbeats.
        """
        try:
            while not self.shutdown_event.is_set():
                self.send_hearbeat_event()
                # Hier kann IO-Logik implementiert werden
                time.sleep(1)
        except Exception as exc:
            self.logger.error(f"Exception {self.name}: {exc}")
        self.logger.debug(f"Close {self.name}")
        time.sleep(1)


class DbProcess(BaseProcess):
    """
    Beispielprozess für Datenbank-Aufgaben, der mit Queues und Event arbeitet.
    Sendet regelmäßig einen Heartbeat.
    """

    def __init__(
        self,
        name: str,
        queue_server: MyQueue,
        queue_io: MyQueue,
        queue_db: MyQueue,
        event_shutdown: MyEvent,
        event_heartbeat: MyEvent
    ):
        super().__init__(name=name, event_shutdown=event_shutdown,
                         event_heartbeat=event_heartbeat)
        # DB liest nur von queue_db, schreibt aber auf queue_server und queue_io
        self.queue_server: WriteOnlyQueue = WriteOnlyQueue(queue_server)
        self.queue_io: WriteOnlyQueue = WriteOnlyQueue(queue_io)
        self.queue_db: ReadOnlyQueue = ReadOnlyQueue(queue_db)
        self.shutdown_event = event_shutdown

    def run(self):
        """
        Hauptschleife des DB-Prozesses. Prüft regelmäßig das Shutdown-Event und sendet Heartbeats.
        """
        try:
            while not self.shutdown_event.is_set():
                self.send_hearbeat_event()
                # Hier kann DB-Logik implementiert werden
                time.sleep(1)
        except Exception as exc:
            self.logger.error(f"Exception {self.name}: {exc}")
        self.logger.debug(f"Close {self.name}")
        time.sleep(1)


class ProcessManager:
    """
    Zentrale Klasse zur Verwaltung und Kontrolle aller Prozesse im System.
    Bietet Methoden zum Starten, Stoppen, Überwachen (Heartbeat) und Beenden der Prozesse.
    """
    processes: Dict[str, BaseProcess] = {}

    @classmethod
    def getActiveCount(cls) -> int:
        """
        Gibt die Anzahl aktiver Prozesse zurück (inkl. MainProcess).
        :return: Anzahl Prozesse
        """
        return len(multiprocessing.active_children()) + 1

    @classmethod
    def getCurrentProcessName(cls) -> str:
        """
        Gibt den Namen des aktuellen Prozesses zurück.
        :return: Prozessname
        """
        return multiprocessing.current_process().name

    @classmethod
    def getCurrentProcessPid(cls):
        """
        Gibt die PID des aktuellen Prozesses zurück.
        :return: Prozess-ID
        """
        return multiprocessing.current_process().pid

    @classmethod
    def getListOfProcessesAsText(cls) -> str:
        """
        Gibt eine kommaseparierte Liste aller aktiven Kindprozesse zurück.
        :return: Prozessnamen als String
        """
        return ", ".join([p.name for p in multiprocessing.active_children()])

    @classmethod
    def getListOfProcesses(cls) -> list[BaseProcess]:
        """
        Gibt eine Liste der aktiven Processe zurück.
        """
        return multiprocessing.active_children()

    @classmethod
    def is_alive(cls, name) -> bool:
        """
        Prüft, ob ein bestimmter Prozess noch läuft.
        :param name: Name des Prozesses
        :return: True, wenn Prozess läuft, sonst False
        """
        alive: bool = False
        if name in cls.processes:
            alive = cls.processes[name].is_alive()
        return alive

    @classmethod
    def check_heartbeat(cls, name) -> bool:
        """
        Prüft für den angegebenen Prozess, ob dessen Heartbeat-Event gesetzt ist.
        Wird vom Hauptprozess im definierten Intervall aufgerufen.
        Falls ein Heartbeat nicht gesetzt ist, wird dies geloggt.
        Nach erfolgreicher Prüfung wird das Event wieder gelöscht (clear).
        :param name: Name des zu prüfenden Prozesses
        :return: True, wenn Heartbeat gesetzt war, sonst False

        NEU: Diese Methode prüft explizit **nur einen** Prozess anhand des Namens.
        Die Hilfsmethoden __get_event_heartbeat und __clear_event_heartbeat werden verwendet,
        um das Event abzufragen bzw. zurückzusetzen.
        """
        state: bool = True

        if not cls.__get_event_heartbeat(name=name):
            state = False
        else:
            cls.__clear_event_heartbeat(name=name)

        return state

    @classmethod
    def init_process(cls, name: str, queue_server: MyQueue, queue_io: MyQueue, queue_db: MyQueue,
                     event_shutdown: MyEvent, event_heartbeat: MyEvent, handler_process: BaseProcess) -> None:
        """
        Initialisiert und registriert einen neuen Prozess im Manager.
        :param name: Name des Prozesses
        :param queue_server: Server-Queue
        :param queue_io: IO-Queue
        :param queue_db: DB-Queue
        :param event_shutdown: Shutdown-Event für den Prozess
        :param event_heartbeat: Heartbeat-Event für den Prozess
        :param handler_process: Prozessklasse, die instanziiert werden soll
        """
        cls.processes[name] = handler_process(
            name=name,
            queue_server=queue_server,
            queue_io=queue_io,
            queue_db=queue_db,
            event_shutdown=event_shutdown,
            event_heartbeat=event_heartbeat
        )

    @classmethod
    def shutdown_process(cls, name) -> None:
        """
        Beendet einen spezifischen Prozess durch Setzen des Shutdown-Events
        und wartet auf dessen Ende.
        :param name: Name des Prozesses
        """
        if name in cls.processes:
            cls.__set_event_shutdown(name=name)
            cls.join_process(name=name)

    @classmethod
    def start_process(cls, name) -> None:
        """
        Startet einen spezifischen Prozess.
        :param name: Name des Prozesses
        """
        if name in cls.processes:
            cls.processes[name].start()

    @classmethod
    def start_all_process(cls) -> None:
        """
        Startet alle registrierten Prozesse.
        """
        for name in cls.processes:
            cls.processes[name].start()

    @classmethod
    def join_process(cls, name) -> None:
        """
        Wartet auf das Ende eines spezifischen Prozesses.
        :param name: Name des Prozesses
        """
        if name in cls.processes:
            cls.processes[name].join()
            # cls.processes.pop(name) # Fehler mit Dict wenn es ausgeführt wird

    @classmethod
    def terminate_process(cls, name) -> None:
        """
        Erzwingt das sofortige Beenden eines Prozesses (unsanft!).
        :param name: Name des Prozesses
        """
        if name in cls.processes:
            cls.processes[name].terminate()
            cls.join_process(name=name)

    @classmethod
    def __set_event_shutdown(cls, name) -> None:
        cls.processes[name].event_shutdown.set()

    @classmethod
    def __get_event_heartbeat(cls, name):
        return cls.processes[name].event_heartbeat.is_set()

    @classmethod
    def __clear_event_heartbeat(cls, name) -> None:
        cls.processes[name].event_heartbeat.clear()
