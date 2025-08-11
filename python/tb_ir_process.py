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
import multiprocessing
import time
from models.tb_dataclasses import QueueMessage, QueueTestEvents, QueuesMembers
from logging import Logger
from tb_events import IrEvents
from tb_queues import SystemQueues

class Tb_IrProcess(multiprocessing.Process):
    """
    Basisklasse für alle Prozesse im System, die mit dem Server kommunizieren.
    """
    def __init__(self, name: str, logger: Logger, events: IrEvents, queues : SystemQueues) -> None:
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
        # Name prüfen: String, min. 3, max. 50 Zeichen
        if not (3 <= len(name) <= 50):
            raise ValueError("Name muss zwischen 3 und 50 Zeichen lang sein.")
        super().__init__(name=name)
        self.logger = logger
        self.events = events
        
        self.queues : SystemQueues = queues
        self.logger.debug(f"{self.__class__.__name__} - {self.name} init")

    def shutdown(self):
        """
        Setzt das Shutdown-Event, um den Prozess zu beenden.
        """
        if not self.events.shutdown.is_set():
            self.events.shutdown.set()
            self.logger.debug(f"{self.__class__.__name__} - {self.name} called shutdown")
   
    def run(self) -> None:
        self.logger.debug(f"{self.__class__.__name__} - {self.name} running")
        while not self.events.shutdown.is_set():
            msg_in = self.queues.ir.get()    
               
            if not self.queue_test_send_ack(msg=msg_in):
                self.events.error.set()
            self.events.heartbeat.set()
            time.sleep(0.1)
             
        if self.events.shutdown.is_set():
            self.events.shutdown.clear()
        time.sleep(1)
        
    def queue_test_send_ack(self, msg : QueueMessage | None) -> bool:
        status : bool = False
        try:
            if not msg is None:
                if msg.event == QueueTestEvents.REQ_FROM_MAIN_TO_IR:
                    queue_test_msg_ack : QueueMessage = QueueMessage(source=QueuesMembers.IR,dest=QueuesMembers.MAIN,
                        event=QueueTestEvents.ACK_FROM_IR_TO_MAIN, timestamp=time.time(), data = "")
                    if not self.queues.main.put(item=queue_test_msg_ack):
                        status = False
                    else:
                        status = True
        except Exception:
            status = False
        return status