import multiprocessing
from multiprocessing import Queue, Event
import time
from models.myDataclasses import QueueMessage
from typing import Optional, Dict, Any, Callable
from dataclasses import dataclass, field
import socketio
from threading import Thread

MAXIMUM_TIMEOUT: int = 10
QUEUE_MAXSIZE: int = 128
    
class MyEvent:
    """
    Wrapper-Klasse für multiprocessing.Event, um einen einheitlichen Umgang mit Events zu ermöglichen.
    """

    def __init__(self) -> None:
        self._event = multiprocessing.Event()

    def is_set(self) -> bool:
        return self._event.is_set()

    def set(self) -> None:
        self._event.set()

    def clear(self) -> None:
        self._event.clear()

    def wait(self, timeout: Optional[int] = None) -> bool:
        return self._event.wait(timeout)

@dataclass
class ServerEvents:
    shutdown: MyEvent = field(default_factory=MyEvent)
    heartbeat: MyEvent = field(default_factory=MyEvent)
    connect: MyEvent = field(default_factory=MyEvent)
    disconnect: MyEvent = field(default_factory=MyEvent)
    message: MyEvent = field(default_factory=MyEvent)
    alarm: MyEvent = field(default_factory=MyEvent)
    error_on_connection: MyEvent = field(default_factory=MyEvent)
    error_from_server_process : MyEvent  = field(default_factory=MyEvent)
    server_process_okay : MyEvent  = field(default_factory=MyEvent)

class MyQueue:
    """
    Wrapper für multiprocessing.Queue mit fester Maximalgröße.
    """

    def __init__(self) -> None:
        self._queue: Queue[QueueMessage] = Queue(maxsize=QUEUE_MAXSIZE)

    def put(self, item: QueueMessage, block: bool = False, timeout: Optional[float] = 0) -> None:
        self._queue.put(item, block, timeout)

    def get(self, block: bool = False, timeout: Optional[float] = 0) -> QueueMessage:
        return self._queue.get(block, timeout)

class WriteOnlyQueue:
    """
    Queue-Wrapper, der ausschließlich das Schreiben (put) erlaubt.
    """

    def __init__(self, queue: MyQueue) -> None:
        self._queue: MyQueue = queue

    def put(self, item: QueueMessage, block: bool = False, timeout: Optional[float] = 0) -> None:
        return self._queue.put(item=item, block=block, timeout=timeout)

    def get(self, block: bool = False, timeout: Optional[float] = 0) -> QueueMessage:
        raise RuntimeError("This queue is write-only!")

class ReadOnlyQueue:
    """
    Queue-Wrapper, der ausschließlich das Lesen (get) erlaubt.
    """

    def __init__(self, queue: MyQueue) -> None:
        self._queue: MyQueue = queue

    def get(self, block: bool = False, timeout: Optional[float] = 0) -> QueueMessage:
        return self._queue.get(block=block, timeout=timeout)

    def put(self, item: QueueMessage, block: bool = False, timeout: Optional[float] = 0) -> None:
        raise RuntimeError("This queue is read-only!")

class MyTimerThread(Thread):
    """
    Timer-Thread, der nach Ablauf eines Intervalls eine Funktion ausführt.
    Beispiel:
        t = MyTimerThread("Timer1", logger, 30, f)
        t.start()
        t.abort()    # Stoppt den Timer, falls noch nicht ausgelöst
        t.restart()  # Startet den Timer erneut
    """

    def __init__(self, name: str, logger: Any, interval_s: int, function: Callable, shutdown : MyEvent):
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
        """Stop the timer if it hasn't finished yet."""
        if not self._is_error:
            self._is_aborted = True
            self._expired.set()
            
    def restart(self):
        """Startet den Timer erneut."""
        if not self._is_error:
            self._start_again.set()

    def shutdown(self):
        if not self.event_shutdown.is_set():
            self.event_shutdown.set()

    def run(self):
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
        self._is_aborted = False
        if self._expired.is_set():
            self._expired.clear()

        if self._start_again.is_set():
            self._start_again.clear()
    
class user_input(Thread):
    def __init__(self, logger : Any, aborted : MyEvent, shutdown : MyEvent):
        super().__init__(name="user_input")
        self.logger = logger
        self.event_user_aborted : MyEvent = aborted
        self.event_shutdown : MyEvent = shutdown

    def shutdown(self):
        if not self.event_shutdown.is_set():
            self.event_shutdown.set()

    def run(self):
        while not self.event_shutdown.is_set():
            if input() == 'q' :
                self.event_user_aborted.set()
                self.logger.debug(f"User q pressed")
            time.sleep(0.1)
        
        if self.event_shutdown.is_set():
            self.logger.debug(f"User input shutdown successfully")

class ServerProcess(multiprocessing.Process):
    """
    Basisklasse für alle Prozesse im System.
    """
    logger: Any
    url: str
    events: ServerEvents
    in_konfig_modus: bool
    is_connected: bool
    sio: socketio.Client
    is_connected_error : bool

    def __init__(self, logger: Any, name: str, url: str, events: ServerEvents) -> None:
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

        self.in_konfig_modus: bool = False
        self.is_connected: bool = False
        self.is_connected_error : bool = False

        self.sio: socketio.Client = socketio.Client(
            reconnection=False,
            reconnection_attempts=0,
            reconnection_delay_max=5,
            handle_sigint=False
        )

        self._register_sio_events()
        
    def _register_sio_events(self) -> None:
        @self.sio.event
        def connect() -> None:
            self.is_connected = True
            self.is_connected_error = False
            self.events.connect.set()
            self.logger.debug(f"Verbindung zu {self.url} über {self.sio.transport()} erfolgreich!")

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
                self.logger.debug(f"Connection error: {data}")
                self.is_connected_error = True

        @self.sio.event
        def message(data: Optional[Any] = None) -> None:
            self.events.message.set()
            self.logger.debug(f"server_message: {data}")

        @self.sio.event
        def alarm(data: Optional[Any] = None) -> None:
            self.events.alarm.set()
            self.logger.debug(f"alarm: {data}")

        @self.sio.event
        def on_konfig_start() -> None:
            self.in_konfig_modus = True
            self.logger.debug("konfig_start")

        @self.sio.event
        def on_konfig_ende() -> None:
            self.in_konfig_modus = False
            self.logger.debug("konfig_ende")

    def shutdown(self):
        if not self.events.shutdown.is_set():
            self.events.shutdown.set()

    def reset(self) -> bool:
        self.state : bool = True
        if self.is_connected :
            self.sio.disconnect()
            self.is_connected = False
            self.state = self.events.disconnect.wait(timeout=MAXIMUM_TIMEOUT)
        return self.state
    
    def run(self) -> None:
        self.logger.debug("ServerProcess gestartet")

        while not self.events.shutdown.is_set():
            if  self.events.error_on_connection.is_set():
                self.events.error_on_connection.clear()
                self.events.error_from_server_process.set()

            if not self.is_connected_error:
                if not self.events.server_process_okay.is_set():
                    self.events.server_process_okay.set()
        
            if not self.is_connected:
                try:
                    self.sio.connect(self.url, transports="websocket")
                    self.is_connected = self.events.connect.wait(timeout=MAXIMUM_TIMEOUT)
                except Exception:
                    self.is_connected = False
            self.events.heartbeat.set()
            time.sleep(1)
        
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
        return len(multiprocessing.active_children()) + 1

    @classmethod
    def getCurrentProcessName(cls) -> str:
        return multiprocessing.current_process().name

    @classmethod
    def getCurrentProcessPid(cls) -> int:
        return multiprocessing.current_process().pid

    @classmethod
    def getListOfProcessesAsText(cls) -> str:
        return ", ".join([p.name for p in multiprocessing.active_children()])

    @classmethod
    def getListOfProcesses(cls) -> list[multiprocessing.Process]:
        return multiprocessing.active_children()

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
