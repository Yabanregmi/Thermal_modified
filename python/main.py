import logging
#import keyboard
import time
from my_processes import (
    ProcessManager,
    ServerProcess
)
from global_mp_logger import GlobalMPLogger as my_logger
from my_processes import ServerEvents
from pathlib import Path
from config import SERVER_URL
from my_relais import Relay

def shutdown_all_processes():
    for name in ProcessManager.processes:
        ProcessManager.shutdown_process(name=name)
    # for name in ProcessManager.processes:
    #     ProcessManager.join_process(name=name)


def check_all_heartbeats() -> list[ServerProcess]:
    failed_processes: list[ServerProcess] = []

    for name in ProcessManager.processes:
        if not ProcessManager.check_heartbeat(name=name):
            failed_processes.append(ProcessManager.processes[name])

    return failed_processes

def critical_error_loop(logger):
    """Endlosschleife im kritischen Fehlerfall – nur durch Neustart zu beenden."""
    logger.critical("Kritischer Fehler: Programm befindet sich in Fehler-Endlosschleife. Neustart erforderlich!")
    Relay.off_1()  # Alle Relais ggf. abschalten, je nach Sicherheitskonzept
    while True:
        time.sleep(10)  # CPU schonen, aber Zustand beibehalten


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
    # Logger initialisieren
    my_logger.configure(Path("log.txt"), logging.DEBUG)
    my_logger.start()

    logger_main_process = my_logger.get_logger("mainprozess")
    logger_server_process = my_logger.get_logger("serverprozess")
    logger_relais = my_logger.get_logger("relais")

    Relay.init(logger=logger_relais, bus_nr=1)
    Relay.on_1()

    server_events: ServerEvents = ServerEvents()
    last_heartbeat: float = time.time()

    server_process = ServerProcess(logger=logger_server_process, name="Server", url=SERVER_URL, events=server_events)
    server_process.start()

    try:
        while True:
            try:
                if server_events.error_from_server_process.is_set():
                    Relay.on_3()
                    server_events.error_from_server_process.clear()

                if server_events.server_process_okay.is_set():
                    Relay.off_3()
                    server_events.server_process_okay.clear()

                if server_events.heartbeat.is_set():
                    server_events.heartbeat.clear()

                now = time.time()
                if now - last_heartbeat >= HEARTBEAT_INTERVAL:
                    for failed_process in check_all_heartbeats():
                        logger_main_process.critical(f"{failed_process} heartbeat failed")
                        Relay.off_1()
                    last_heartbeat = now

                time.sleep(1)
            except Exception as e:
                logger_main_process.critical(f"Critical process error: {e}", exc_info=True)
                server_process.terminate()
                # Keine break-Anweisung mehr, sondern in Fehler-Endlosschleife springen:
                critical_error_loop(logger_main_process)
                Relay.off_1()
    finally:
        Relay.off_1()
        for process in ProcessManager.processes.values():
            process.join()
        my_logger.stop()
