"""
Dieses Modul stellt eine robuste Infrastruktur für die Verwaltung,
Überwachung und Kommunikation von Multiprozess-Systemen bereit.

Enthalten sind Wrapper-Klassen für Events und Queues, 
spezialisierte Thread- und Prozessklassen sowie ein zentrales Prozess-Management.
Die Architektur ermöglicht die sichere und flexible Steuerung von Serverprozessen 
mit Hilfe von Events, Timern und interprozessualer Kommunikation.

Hauptbestandteile:
- MyEvent: Wrapper für multiprocessing.Event für einen einheitlichen Umgang mit Events.
- ServerEvents: Dataclass zur Bündelung aller relevanten Events für Serverprozesse.
- MyQueue, WriteOnlyQueue, ReadOnlyQueue: Wrapper für multiprocessing.Queue
    mit Zugriffsbeschränkungen.
- MyTimerThread: Thread-basierter Timer zur wiederholten Ausführung von Funktionen.
- user_input: Thread zur Verarbeitung von Benutzereingaben zur Laufzeitkontrolle.
- ServerProcess: Basisklasse für Prozesse mit serverseitiger Kommunikation (z.B. über SocketIO).
- ProcessManager: Zentrale Klasse zur Verwaltung, Überwachung, Steuerung und Terminierung 
    aller Prozesse im System.

Typische Anwendungsfälle:
- Steuerung und Überwachung von Serverprozessen in verteilten Systemen.
- Sichere Kommunikation und Synchronisation zwischen Prozessen und Threads.
- Einfache Erweiterbarkeit für weitere Prozess- und Eventtypen.

Abhängigkeiten:
- multiprocessing, threading, socketio, time, dataclasses, typing

Hinweis:
Dieses Modul ist für den Einsatz in Systemen mit hohen Anforderungen an Parallelität, 
Zuverlässigkeit und Wartbarkeit konzipiert.
"""
from ast import Pass
from typing import Dict, Any, Callable
import multiprocessing
from threading import Thread
import time
from dataclasses import dataclass, field
from multiprocessing import Queue, Event
from xmlrpc.client import boolean
import socketio
from models.myDataclasses import QueueMessage

MAXIMUM_TIMEOUT: int = 10
QUEUE_MAXSIZE: int = 128

class MyEvent:
    """
    Wrapper-Klasse für multiprocessing.Event, um einen 

    einheitlichen Umgang mit Events zu ermöglichen.
    """

    def __init__(self) -> None:
        """
        Initialisiert das interne Event-Objekt.
        """
        self._event = multiprocessing.Event()

    def is_set(self) -> bool:
        """
        Prüft, ob das Event gesetzt ist.

        Returns:
            bool: True, wenn das Event gesetzt ist, sonst False.
        """
        return self._event.is_set()

    def set(self) -> None:
        """
        Setzt das Event.
        """
        self._event.set()

    def clear(self) -> None:
        """
        Löscht das Event (setzt es zurück).
        """
        self._event.clear()

    def wait(self, timeout: int | None = None) -> bool:
        """
        Wartet, bis das Event gesetzt wird oder das Timeout abläuft.

        Args:
            timeout (Optional[int]): Maximale Wartezeit in Sekunden.

        Returns:
            bool: True, wenn das Event gesetzt wurde, sonst False.
        """
        return self._event.wait(timeout = 0)


@dataclass
class ServerEvents:
    """
    Sammlung von Events zur Steuerung und Überwachung des Server-Prozesses.
    """
    shutdown: MyEvent = field(default_factory=MyEvent)
    heartbeat: MyEvent = field(default_factory=MyEvent)
    connect: MyEvent = field(default_factory=MyEvent)
    disconnect: MyEvent = field(default_factory=MyEvent)
    message: MyEvent = field(default_factory=MyEvent)
    alarm: MyEvent = field(default_factory=MyEvent)
    error_on_connection: MyEvent = field(default_factory=MyEvent)
    error_from_server_process: MyEvent = field(default_factory=MyEvent)
    server_process_okay: MyEvent = field(default_factory=MyEvent)
    
class MyQueue:
    """
    Wrapper für multiprocessing.Queue mit fester Maximalgröße.
    """

    def __init__(self) -> None:
        """
        Initialisiert die interne Queue mit fester Maximalgröße.
        """
        self._queue: Queue = Queue(maxsize=QUEUE_MAXSIZE)

    def put(self, item: QueueMessage) -> bool:
        """
        Fügt ein Element zur Queue hinzu, falls Platz ist.
        Args:
            item (QueueMessage): Das hinzuzufügende Element.
        Returns:
            bool: True, wenn das Element hinzugefügt wurde, sonst False.
        """
        if not self._queue.full():
            self._queue.put_nowait(item)
            return True
        return False

    def get(self) -> QueueMessage | None:
        """
        Entnimmt ein Element aus der Queue.
        Returns:
            Optional[QueueMessage]: Das entnommene Element oder None, falls leer.
        """
        if not self._queue.empty():
            return self._queue.get_nowait()
        return None
    
    def join(self) -> None:
        self._queue.close()
        self._queue.join_thread()
        


class WriteOnlyQueue:
    """
    Queue-Wrapper, der ausschließlich das Schreiben (put) erlaubt.
    """

    def __init__(self, queue: MyQueue) -> None:
        """
        Initialisiert die WriteOnlyQueue mit einer existierenden MyQueue.
        """
        self._queue: MyQueue = queue

    def put(self, item: QueueMessage, block: bool = False, timeout: float | None = 0) -> bool:
        """
        Fügt ein Element zur Queue hinzu.

        Args:
            item (QueueMessage): Das hinzuzufügende Element.
            block (bool): Ob blockierend gewartet werden soll.
            timeout (Optional[float]): Maximale Wartezeit.
        """
        return self._queue.put(item=item)

    def get(self) -> QueueMessage | None:
        """
        Das Lesen aus der Queue ist nicht erlaubt.

        Raises:
            RuntimeError: Diese Queue ist nur zum Schreiben.
        """
        raise RuntimeError("This queue is write-only!")


class ReadOnlyQueue:
    """
    Queue-Wrapper, der ausschließlich das Lesen (get) erlaubt.
    """

    def __init__(self, queue: MyQueue) -> None:
        """
        Initialisiert die ReadOnlyQueue mit einer existierenden MyQueue.
        """
        self._queue: MyQueue = queue

    def get(self) -> QueueMessage | None:
        """
        Entnimmt ein Element aus der Queue.

        Args:
            block (bool): Ob blockierend gewartet werden soll.
            timeout (Optional[float]): Maximale Wartezeit.

        Returns:
            QueueMessage: Das entnommene Element.
        """
        return self._queue.get()

    def put(self) -> None:
        """
        Das Schreiben in die Queue ist nicht erlaubt.

        Raises:
            RuntimeError: Diese Queue ist nur zum Lesen.
        """
        raise RuntimeError("This queue is read-only!")

class MyTimerThread(Thread):
    """
    Timer-Thread, der nach Ablauf eines Intervalls eine Funktion ausführt.

    Beispiel:
        t = MyTimerThread("Timer1", logger, 30, f, shutdown_event)
        t.start()
        t.abort()    # Stoppt den Timer, falls noch nicht ausgelöst
        t.restart()  # Startet den Timer erneut
    """

    def __init__(self, name: str, logger: Any, interval_s: int, function: Callable, 
                    shutdown : MyEvent):
        """
        Initialisiert den Timer-Thread.

        Args:
            name (str): Name des Timers.
            logger (Any): Logger-Objekt.
            interval_s (int): Intervall in Sekunden.
            function (Callable): Auszuführende Funktion nach Ablauf.
            shutdown (MyEvent): Event zum Beenden des Threads.

        Raises:
            ValueError: Bei ungültigen Parametern.
        """
        if logger is None:
            raise ValueError("Logger darf nicht None sein.")
        if function is None:
            raise ValueError("Keine Funktion übergeben")
        if not (3 <= len(name) <= 50):
            raise ValueError("Name muss zwischen 3 und 50 Zeichen lang sein.")

        self._name = name
        self._interval : int = interval_s
        self._function : Callable = function
        self._expired : MyEvent = MyEvent()
        self._start_again : MyEvent= MyEvent()
        self._is_aborted :bool = False
        self._max_timeout :int= 10
        self._logger = logger
        self._is_error :bool = False
        self.event_shutdown : MyEvent = shutdown

        super().__init__(name=name)



    def abort(self):
        """
        Stoppt den Timer, falls er noch nicht ausgelöst wurde.
        """
        if not self._is_error:
            self._is_aborted = True
            self._expired.set()
            
    def restart(self):
        """
        Startet den Timer erneut.
        """
        if not self._is_error:
            self._start_again.set()

    def shutdown(self):
        """
        Setzt das Shutdown-Event, um den Thread zu beenden.
        """
        if not self.event_shutdown.is_set():
            self.event_shutdown.set()

    def run(self):
        """
        Startet den Timer-Thread und ruft nach Ablauf die Funktion auf.
        """
        self._logger.debug(f"Timer {self.name} run")
        self._start_again.set() # Skip first loop query

        while self._start_again.wait(self._max_timeout) and not self._is_error and not self.event_shutdown.is_set():
            try:
                 # User definied waiting 
                self._expired.wait(self._interval)
                if not self._is_aborted:
                    self._function()
                self._is_aborted = False

            except Exception as e:
                self._logger.critical(f"Timer {self.name} unkown error")
                self._is_error = True
        
        self.reset()

        if self.event_shutdown.is_set():
            self._logger.debug(f"Timer {self._name} shutdown successfully")
        
    def reset(self) -> None:
        """
        Setzt den Timer-Zustand zurück.
        """
        self._is_aborted = False
        if self._expired.is_set():
            self._expired.clear()

        if self._start_again.is_set():
            self._start_again.clear()
    
class user_input(Thread):
    """
    Thread zur Verarbeitung von Benutzereingaben, speziell zum Abbruch oder Herunterfahren.
    """
    def __init__(self, logger : Any, aborted : MyEvent, shutdown : MyEvent):
        """
        Initialisiert den user_input-Thread.

        Args:
            logger (Any): Logger-Objekt.
            aborted (MyEvent): Event für Benutzerabbruch.
            shutdown (MyEvent): Event für Shutdown.
        """
        super().__init__(name="user_input")
        self.logger = logger
        self.event_user_aborted : MyEvent = aborted
        self.event_shutdown : MyEvent = shutdown

    def shutdown(self):
        """
        Setzt das Shutdown-Event, um den Thread zu beenden.
        """
        if not self.event_shutdown.is_set():
            self.event_shutdown.set()

    def run(self):
        """
        Wartet auf Benutzereingabe ('q'), um das Abbruch-Event zu setzen.
        """
        while not self.event_shutdown.is_set():
            if input() == 'q' :
                self.event_user_aborted.set()
                self.logger.debug(f"User q pressed")
            time.sleep(0.1)
        
        if self.event_shutdown.is_set():
            self.logger.debug(f"User input shutdown successfully")

class ServerProcess(multiprocessing.Process):
    """
    Basisklasse für alle Prozesse im System, die mit dem Server kommunizieren.
    """
    logger: Any
    url: str
    events: ServerEvents
    in_konfig_modus: bool
    is_connected: bool
    sio: socketio.Client
    is_connected_error : bool

    def __init__(self, logger: Any, name: str, url: str, events: ServerEvents, queue_server : MyQueue, queue_ir : MyQueue, queue_main : MyQueue) -> None:
        """
        Initialisiert den ServerProcess.

        Args:
            logger (Any): Logger-Objekt.
            name (str): Name des Prozesses.
            url (str): Server-URL.
            events (ServerEvents): Events zur Steuerung.

        Raises:
            ValueError: Bei ungültigen Parametern.
        """
        if logger is None:
            raise ValueError("Logger darf nicht None sein.")

        # Name prüfen: String, min. 3, max. 50 Zeichen
        if not (3 <= len(name) <= 50):
            raise ValueError("Name muss zwischen 3 und 50 Zeichen lang sein.")

        # URL prüfen: String, min. 5, max. 200 Zeichen
        if not (5 <= len(url) <= 200):
            raise ValueError("URL muss zwischen 5 und 200 Zeichen lang sein.")

        super().__init__(name=name)
        self.logger = logger
        self.url = url
        self.events = events
        
        self.queue_server : MyQueue = queue_server
        self.queue_ir : MyQueue = queue_ir
        self.queue_main : MyQueue = queue_main

        self.in_konfig_modus: bool = False
        self.is_connected: bool = False
        self.is_connected_error : bool = False

        self.sio: socketio.Client = socketio.Client(
            reconnection=False,
            reconnection_attempts=0,
            reconnection_delay_max=5,
            handle_sigint=False
        )
        
        self.dict_send_to_backend = {
            "ack_config" : lambda data : self.sio.emit(event="ack_config", data = data, callback = lambda : self.logger.warning("ack_config")),
            "ack_tempreture" : lambda data : self.sio.emit(event="ack_tempreture", data = data, callback = lambda : self.logger.warning("ack_tempreture")),
            "timeout_stop_record" : lambda data : self.sio.emit(event="timeout_stop_record", data = data, callback = lambda : self.logger.warning("timeout_stop_record")),
            "send_live_tempreture" : lambda data : self.sio.emit(event="send_live_tempreture", data = data, callback = lambda : self.logger.warning("send_live_tempreture")),
            "ack_call_live_tempreture" : lambda data : self.sio.emit(event="ack_call_live_tempreture", data = data, callback = lambda : self.logger.warning("ack_call_live_tempreture")),
            "ack_send_live_tempreture" : lambda data : self.sio.emit(event="ack_send_live_tempreture", data = data, callback = lambda : self.logger.warning("ack_send_live_tempreture")),
        }
        
        @self.sio.event
        def connect() -> None:
            self.is_connected = True
            self.is_connected_error = False
            self.events.connect.set()
            self.logger.debug(f"Verbindung url: {self.url} protocol: {self.sio.transport()} sid: {self.sio.get_sid()} erfolgreich!")

        @self.sio.event
        def disconnect() -> None:
            self.is_connected = False
            self.events.disconnect.set()
            self.logger.debug(f"Verbindung zu {self.url} wegen Reason {getattr(self.sio, 'reason', 'unbekannt')} beendet!")

        @self.sio.event
        def connect_error(data: Any) -> None:
            self.is_connected = False
            self.events.error_on_connection.set()

            if not self.is_connected_error :
                self.logger.warning(f"Connection error: {data}")
                self.is_connected_error = True

        @self.sio.event
        def reset_alarm() -> None:
            self.logger.warning("reset alarm")
            
        @self.sio.event
        def reset_error() -> None:
            self.logger.warning("reset alarm")
            
        @self.sio.event
        def set_config() -> None:
            self.logger.warning("set config")

        @self.sio.event
        def set_tempreture(data) -> None:
            self.logger.warning(f"set tempreture {data}")
            
        @self.sio.event
        def manual_start_record() -> None:
            self.logger.warning("manual start record")

        @self.sio.event
        def manual_stop_record() -> None:
            self.logger.warning("manual stop record")

        @self.sio.event
        def manual_call_record() -> None:
            self.logger.warning("manual call record")
            
        @self.sio.event
        def call_live_tempreture() ->None:
            self.logger.warning("call live tempreture")
            
        @self.sio.event
        def call_history_tempreture() -> None:
            self.logger.warning("call history tempreture")
            
        @self.sio.event
        def message(data) -> None:
            self.events.message.set()

    def shutdown(self):
        """
        Setzt das Shutdown-Event, um den Prozess zu beenden.
        """
        if not self.events.shutdown.is_set():
            self.events.shutdown.set()

    def reset(self) -> bool:
        """
        Setzt den Prozess zurück und trennt die Verbindung.

        Returns:
            bool: True, wenn die Verbindung erfolgreich getrennt wurde, sonst False.
        """
        self.state : bool = True
        if self.is_connected :
            self.sio.shutdown()
            self.sio.disconnect()
            self.is_connected = False
            self.state = self.events.disconnect.wait(timeout=MAXIMUM_TIMEOUT)
        return self.state
    
    def server_ack(self) -> None:
        """
        Callback-Funktion für Server-Bestätigungen.
        """
        self.logger.debug("Server ack")

    def send_to_backend(self, msg : QueueMessage):
        if msg.command in self.dict_send_to_backend:
            self.logger.debug("Send ack_config to backend")
            self.sio.emit(event="ack_config", data = "Hallo")


    def run(self) -> None:
        """
        Führt die Hauptlogik des Server-Prozesses aus.
        """
        self.logger.debug("ServerProcess run gestartet")

        while not self.events.shutdown.is_set():
            if self.events.message.is_set():
                self.events.message.clear()
                self.sio.emit(event='Client ack', data = "Hallo vom Client", callback=self.server_ack)

            if  self.events.error_on_connection.is_set():
                self.events.error_on_connection.clear()
                self.events.error_from_server_process.set()

            if not self.is_connected_error:
                if not self.events.server_process_okay.is_set():
                    self.events.server_process_okay.set()
        
            if not self.is_connected:
                try:
                    self.sio.connect(self.url, transports=["websocket"])
                    self.is_connected = self.events.connect.wait(timeout=MAXIMUM_TIMEOUT)
                except Exception:
                    self.is_connected = False
            else:
                msg = self.queue_server.get()
                if not msg is None:
                    self.send_to_backend(msg = msg)
        
            self.events.heartbeat.set()
            time.sleep(0.1)
        
        if not self.reset():
            self.logger.debug("ServerProcess shutdown error")
        else:
            self.logger.debug("ServerProcess shutdown successfully")
        time.sleep(1)

class ProcessManager:
    """
    Zentrale Klasse zur Verwaltung und Kontrolle aller Prozesse im System.
    """
    processes: Dict[str, ServerProcess] = {}

    @classmethod
    def getActiveCount(cls) -> int:
        """
        Gibt die Anzahl der aktiven Prozesse zurück.

        Returns:
            int: Anzahl aktiver Prozesse.
        """
        return len(multiprocessing.active_children()) + 1

    @classmethod
    def getCurrentProcessName(cls) -> str:
        return multiprocessing.current_process().name

    @classmethod
    def getCurrentProcessPid(cls) -> int | None:
        return multiprocessing.current_process().pid

    @classmethod
    def getListOfProcessesAsText(cls) -> str:
        return ", ".join([p.name for p in multiprocessing.active_children()])

    @classmethod
    def is_alive(cls, name: str) -> bool:
        alive: bool = False
        if name in cls.processes:
            alive = cls.processes[name].is_alive()
        return alive

    @classmethod
    def check_heartbeat(cls, name: str) -> bool:
        state: bool = True
        if not cls.__get_event_heartbeat(name=name):
            state = False
        else:
            cls.__clear_event_heartbeat(name=name)
        return state

    @classmethod
    def shutdown_process(cls, name: str) -> None:
        if name in cls.processes:
            cls.__set_event_shutdown(name=name)
            cls.join_process(name=name)

    @classmethod
    def start_process(cls, name: str) -> None:
        if name in cls.processes:
            cls.processes[name].start()

    @classmethod
    def start_all_process(cls) -> None:
        for name in cls.processes:
            cls.processes[name].start()

    @classmethod
    def join_process(cls, name: str) -> None:
        if name in cls.processes:
            cls.processes[name].join()

    @classmethod
    def terminate_process(cls, name: str) -> None:
        if name in cls.processes:
            cls.processes[name].terminate()
            cls.join_process(name=name)

    @classmethod
    def __set_event_shutdown(cls, name: str) -> None:
        cls.processes[name].events.shutdown.set()

    @classmethod
    def __get_event_heartbeat(cls, name: str) -> bool:
        return cls.processes[name].events.heartbeat.is_set()

    @classmethod
    def __clear_event_heartbeat(cls, name: str) -> None:
        cls.processes[name].events.heartbeat.clear()
