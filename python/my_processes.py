import multiprocessing
from multiprocessing import Process, Queue, Event
import time
from venv import logger

import socketio.async_client
import socketio.exceptions
from models.myDataclasses import QueueMessage
from typing import Optional, Dict
from dataclasses import dataclass, field
import socketio
import asyncio
import random
from datetime import datetime

from ringbuffer import RingBuffer
from config import BUFFER_SIZE, SERVER_URL, SLEEP_TIME
from checksums import get_batch_checksum, get_crc
import time
from typing import Optional, Dict
import logging
from global_mp_logger import GlobalMPLogger
# Maximale Wartezeit für bestimmte Operationen (in Sekunden)
MAXIMUM_TIMEOUT: int = 1
# Maximale Größe der Queue (Anzahl Nachrichten)
QUEUE_MAXSIZE: int = 128

class MyEvent():
    """
    Wrapper-Klasse für multiprocessing.Event, um einen einheitlichen Umgang mit Events zu ermöglichen.
    Wird genutzt, um prozessübergreifende Signale (z.B. Heartbeat oder Shutdown) zu setzen und abzufragen.
    """

    def __init__(self):
        """Erzeugt ein neues multiprocessing.Event für die Synchronisation zwischen Prozessen."""
        self._event = multiprocessing.Event()

    def is_set(self) -> bool:
        """Gibt zurück, ob das Event aktuell gesetzt ist (True/False)."""
        return self._event.is_set()

    def set(self) -> None:
        """Setzt das Event (signalisiert allen wartenden Prozessen das Ereignis)."""
        self._event.set()

    def clear(self) -> None:
        """Löscht das Event (setzt es auf 'nicht gesetzt')."""
        self._event.clear()

    def wait(self, timeout : None | int =None) -> bool:
        """
        Blockiert, bis das Event gesetzt ist oder ein Timeout auftritt.
        :param timeout: Maximale Wartezeit in Sekunden (oder None für unendlich)
        :return: True, wenn das Event gesetzt wurde, sonst False (bei Timeout)
        """
        return self._event.wait(timeout)

@dataclass
class ServerEvents:
    shutdown: MyEvent = field(default_factory=MyEvent)
    heartbeat: MyEvent = field(default_factory=MyEvent)
    connect: MyEvent = field(default_factory=MyEvent)
    disconnect: MyEvent = field(default_factory=MyEvent)
    message: MyEvent = field(default_factory=MyEvent)
    alarm: MyEvent = field(default_factory=MyEvent)

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

class BaseProcess(multiprocessing.Process):
    """
    Basisklasse für alle Prozesse im System.
    Stellt die gemeinsame Schnittstelle für Shutdown- und Heartbeat-Events bereit.
    """
    def __init__(self, logger, name: str, url : str, events : ServerEvents):
        """
        :param name: Name des Prozesses (zur Identifikation und für Logging)
        :param event_shutdown: Event-Objekt für das Beenden des Prozesses
        :param event_heartbeat: Event-Objekt für Heartbeat-Signalisierung
        """
        super().__init__(name=name)
        self.events : ServerEvents = events

        self.logger = logger
        self.name: str = name
        self.url: str = url
        self.in_konfig_modus: bool = False
        self.server_connected: bool = False
        self.is_connected: bool = False
        self.sio: socketio.AsyncClient = socketio.AsyncClient(reconnection=True,reconnection_attempts=3,reconnection_delay_max=5)
        
        @self.sio.event
        async def connect()  -> None:
            self.is_connected = True
            self.events.connect.set()
            self.logger.debug(f"Verbindung zu {self.url} erfolgreich!")

        @self.sio.on('disconnect')
        async def disconnect()  -> None:
            self.is_connected = False
            self.events.disconnect.set()
            self.logger.debug(f"Verbindung zu {self.url} beendet!")

        @self.sio.on('server_message')
        async def message()  -> None:
            self.events.message.set()
            self.logger.debug("server_message")

        @self.sio.on('alarm')
        async def alarm()  -> None:
            self.events.alarm.set()
            self.logger.debug("alarm")

        @self.sio.on('konfig_start')
        async def on_konfig_start()  -> None:
            self.in_konfig_modus = True
            self.logger.debug("konfig_start")
            #await self.sio.emit("konfigReady")  # Rückmeldung an den Server

        @self.sio.on('konfig_ende')
        async def on_konfig_ende() -> None:
            self.in_konfig_modus = False
            self.logger.debug("konfig_ende")
        
    def run(self):
        asyncio.run(self.async_main())
        time.sleep(1)

    async def async_main(self):
        self.logger.debug("ServerProcess gestartet")

        while not self.events.shutdown.is_set():
            if not self.is_connected:
                await self.sio.connect(self.url) # try websocket verbindung
                self.is_connected = self.events.connect.wait() # wait for connect event
            else:
                self.events.heartbeat.set()
        
        self.logger.debug("ServerProcess shutdown initialsiert")
        if self.is_connected:
            await self.sio.disconnect()

            if self.events.disconnect.wait() :
                self.is_connected = False
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
    def getListOfProcesses(cls):
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



# class ServerProcess(BaseProcess):
#     """
#     Beispielprozess für einen Server, der mit mehreren Queues kommuniziert
#     und über ein Event sauber beendet werden kann.
#     Sendet regelmäßig einen Heartbeat an den Hauptprozess.
#     """
#     buffer = RingBuffer(BUFFER_SIZE)

#     def __init__(
#         self,
#         url : str,
#         log_queue,
#         name : str, 
#         events : ServerEvents
#     ):
#         super().__init__(log_queue=log_queue,name = name, event_heartbeat=events.heartbeat, event_shutdown= events.shutdown)
#         self.events : ServerEvents = events
#         self.name: str = name
#         self.url: str = url
#         self.in_konfig_modus: bool = False
#         self.server_connected: bool = False
#         self.is_connected: bool = False
#         self.sio: socketio.AsyncClient = socketio.AsyncClient(reconnection=True,reconnection_attempts=3,reconnection_delay_max=5)

#         @self.sio.on('connect')
#         async def connect(self)  -> None:
#             self.is_connected = True
#             self.events.connect.set()
#             self.logger.debug("connect")
#             #await self.sio.emit('my_event', {'nachricht': 'Hallo Server!'})

#         @self.sio.on('disconnect')
#         async def disconnect(self)  -> None:
#             self.is_connected = False
#             self.events.disconnect.set()
#             self.logger.debug("disconnect")

#         @self.sio.on('server_message')
#         async def message(self)  -> None:
#             self.events.message.set()
#             self.logger.debug("server_message")

#         @self.sio.on('alarm')
#         async def alarm(self)  -> None:
#             self.events.alarm.set()
#             self.logger.debug("alarm")

#         @self.sio.on('konfig_start')
#         async def on_konfig_start(self)  -> None:
#             self.in_konfig_modus = True
#             self.logger.debug("konfig_start")
#             #await self.sio.emit("konfigReady")  # Rückmeldung an den Server

#         @self.sio.on('konfig_ende')
#         async def on_konfig_ende(self) -> None:
#             self.in_konfig_modus = False
#             self.logger.debug("konfig_ende")

# async def async_main(self):
#     attempt: int = 0
#     max_attempts: int = 10  # Maximale Verbindungsversuche

#     while not self.event_shutdown.is_set():
#         try:
#             await self.sio.connect(self.url)
#             self.logger.info(f"Verbindung zu {self.url} erfolgreich!")
#             self.send_hearbeat_event()
#             #await self.sio.wait()  # Wartet, bis die Verbindung getrennt wird
#         except socketio.exceptions.ConnectionError as e:
#             self.logger.error(f"Fehler beim Verbinden zu {self.url}: {e}")
#             attempt += 1
#             if attempt >= max_attempts:
#                 self.logger.error("Maximale Verbindungsversuche erreicht, breche ab.")
#                 break
#             await asyncio.sleep(2)
#         except socketio.exceptions.TimeoutError as e:
#             self.logger.error(f"Server Timeout: {e}")
#             await asyncio.sleep(2)
#         except Exception as e:
#             self.logger.error(f"Unerwarteter Fehler beim Verbindungsaufbau: {e}")
#             await asyncio.sleep(2)
#             break
#         finally:
#             # Verbindung wurde sauber beendet (disconnect), zurücksetzen für erneuten Versuch
#             attempt = 0
#         await asyncio.sleep(1)  # Kleines Delay vor erneutem Verbindungsversuch

#     self.logger.info("Beende async_main.")


           

#         # try:
#         #     while not self.event_shutdown.is_set():
#         #         self.send_hearbeat_event()
#         #         self.startTest()
#         #         await asyncio.sleep(0.01)
#         # except Exception as exc:
#         #     self.logger.error(f"Exception {self.name}: {exc}")
#         # self.logger.debug(f"Close {self.name}")
#         # await self.sio.wait()
#         # await asyncio.sleep(1)
    
#     def run(self):
#         asyncio.run(self.async_main())

#     def startTest(self):
#         wert = round(random.uniform(20.0, 25.0), 1)
#         zeit = datetime.utcnow().isoformat()
#         self.buffer.append((wert, zeit))

#         # Live an den Server senden (mit CRC32-Prüfsumme)
#         if self.is_server_connected():
#             crc = get_crc(wert, zeit)
#             self.send_live_temperatur(wert, zeit, crc)

#         # Nur speichern, wenn NICHT im Konfigmodus!
#         if not self.is_in_konfig_modus() and self.buffer.is_full():
#             values = self.buffer.get_all()
#             batch_checksum = get_batch_checksum(values)
#             db_values = [(wert, zeit, batch_checksum)
#                          for wert, zeit in values]
#             self.logger.debug(
#                 "[DB] Keine Verbindung zur Datenbank; Batch zwischengespeichert.")

#             self.buffer.clear()

#         time.sleep(
#             SLEEP_TIME if not self.is_in_konfig_modus() else 0.2)

#     def connect_to_server(self, server_url, sio):
#         try:
#             self.logger.debug(f"Versuche Verbindung zu {server_url} ...")
#             sio.connect(server_url)
#         except Exception as e:
#             self.logger.error(f"[Server] Fehler bei Verbindung: {e}")

#     def send_live_temperatur(self, wert, zeit, crc):
#         try:
#             print("Temp")
#             sio.emit("liveTemperatur", {
#                 "wert": f"{wert:.1f}",
#                 "zeit": zeit,
#                 "crc": crc
#             })
#         except Exception as e:
#             self.logger.debug(f"[Server] Fehler beim Senden: {e}")

#     def is_in_konfig_modus(self) -> bool:
#         return self.in_konfig_modus

#     def is_server_connected(self) -> bool:
#         return self.server_connected

#     def disconnect(self):
#         try:
#             self.sio.disconnect()
#         except Exception:
#             pass