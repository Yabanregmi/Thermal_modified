print("Hello from Python!")
import logging
import keyboard
import time
from myProcesses import (
    ProcessManager,
    BaseProcess,
    ServerProcess,
    IoProcess,
    DbProcess
)
from myLogger import MyLogger
from myProcesses import MyQueue, MyEvent


def shutdown_all_processes():
    for name in ProcessManager.processes:
        ProcessManager.shutdown_process(name=name)
    # for name in ProcessManager.processes:
    #     ProcessManager.join_process(name=name)


def check_all_heartbeats() -> list[BaseProcess]:
    failed_processes: list[BaseProcess] = []

    for name in ProcessManager.processes:
        if not ProcessManager.check_heartbeat(name=name):
            failed_processes.append(ProcessManager.processes[name])

    return failed_processes


HEARTBEAT_INTERVAL = 3  # Sekunden: Intervall für Heartbeat-Überprüfung

"""
main.py
--------
Startpunkt der Anwendung:
- Initialisiert und verwaltet alle Prozesse (Server, IO, DB)
- Sorgt für zentrales Logging
- Überwacht Heartbeats der Subprozesse im eingestellten Intervall
- Führt einen sauberen Shutdown aller Prozesse per Tastendruck ('q') durch
"""

if __name__ == "__main__":
    # Setzt die eigene Logger-Klasse als Standard für das logging-Modul
    logging.setLoggerClass(MyLogger)

    # Initialisiert den zentralen Logger für den Hauptprozess
    handler_Logger = MyLogger(__name__, sLevel="DEBUG")

    # Erstellt die Queues für die Prozesskommunikation (jeweils eigene Instanzen)
    handler_queue_Server: MyQueue = MyQueue()
    handler_queue_io: MyQueue = MyQueue()
    handler_queue_db: MyQueue = MyQueue()

    # Erstellt die Events für den sauberen Shutdown jedes Prozesses (jeweils eigene Instanzen)
    handler_event_shutdown_server: MyEvent = MyEvent()
    handler_event_shutdown_io: MyEvent = MyEvent()
    handler_event_shutdown_db: MyEvent = MyEvent()

    # Erstellt die Events für den Heartbeat jedes Prozesses (jeweils eigene Instanzen)
    handler_event_heartbeat_server: MyEvent = MyEvent()
    handler_event_heartbeat_io: MyEvent = MyEvent()
    handler_event_heartbeat_db: MyEvent = MyEvent()

    # Speichert Referenzen auf die Prozessklassen (könnten auch direkt übergeben werden)
    handlerServerProcess: ServerProcess = ServerProcess
    handlerIoProcess: IoProcess = IoProcess
    handlerDbProcess: DbProcess = DbProcess

    # Initialisiert Zeitstempel für die Heartbeat-Überwachung
    last_heartbeat: float = time.time()

    # Initialisiert und registriert die Prozesse im ProcessManager
    ProcessManager.init_process(
        name="process_server",
        queue_server=handler_queue_Server,
        queue_io=handler_queue_io,
        queue_db=handler_queue_db,
        event_shutdown=handler_event_shutdown_server,
        event_heartbeat=handler_event_heartbeat_server,
        handler_process=handlerServerProcess,
    )
    ProcessManager.init_process(
        name="process_io",
        queue_server=handler_queue_Server,
        queue_io=handler_queue_io,
        queue_db=handler_queue_db,
        event_shutdown=handler_event_shutdown_io,
        event_heartbeat=handler_event_heartbeat_io,
        handler_process=handlerIoProcess
    )
    ProcessManager.init_process(
        name="process_db",
        queue_server=handler_queue_Server,
        queue_io=handler_queue_io,
        queue_db=handler_queue_db,
        event_shutdown=handler_event_shutdown_db,
        event_heartbeat=handler_event_heartbeat_db,
        handler_process=handlerDbProcess
    )

    handler_Logger.debug(
        f"call {MyLogger.__name__, MyLogger.get_instance_count()}")
    handler_Logger.info(f"{__name__} started")

    # Startet alle registrierten Prozesse
    ProcessManager.start_all_process()

    handler_Logger.debug(
        f"Active processes: {ProcessManager.getActiveCount()}")
    handler_Logger.debug(
        f"Running processes: {ProcessManager.getListOfProcessesAsText()}")

    # Hauptloop: Überwacht Tastendruck 'q' für Shutdown und prüft regelmäßig die Heartbeats aller Prozesse
    while True:
        try:
            # if keyboard.is_pressed('q'):
            #     handler_Logger.debug("CleanUp ressources")
            #     shutdown_all_processes()
            #     break
            # else:
            now = time.time()
            # Prüft alle HEARTBEAT_INTERVAL Sekunden die Heartbeats der Prozesse
            if now - last_heartbeat >= HEARTBEAT_INTERVAL:
                for failed_process in check_all_heartbeats():
                    handler_Logger.critical(
                        f"{failed_process} hearbeat failed")
                last_heartbeat = now
        except Exception as exc:
            handler_Logger.debug(f"Critical error: {exc}")
            # Bei Fehlern werden alle Prozesse sofort unsanft terminiert
            for handler in list(ProcessManager.processes):
                ProcessManager.terminate_process(handler)
        finally:
            # Kurzes Sleep, um CPU-Last zu minimieren und Tastendruck zuverlässig zu erkennen
            time.sleep(0.1)

    # Wartet auf das Ende aller Prozesse, bevor das Programm beendet wird
    for process in ProcessManager.processes.values():
        process.join()

    handler_Logger.debug(
        f"Active processes: {ProcessManager.getActiveCount()}")

    handler_Logger.debug("App close")

    # Stoppt alle Logger-Handler (z.B. für File-Logging)
    handler_Logger.stopAll()
