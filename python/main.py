from asyncio import events
import logging
#import keyboard
import time
from my_processes import (
    ProcessManager,
    BaseProcess
)
from global_mp_logger import GlobalMPLogger as my_logger
from my_processes import MyQueue, MyEvent, ServerEvents
from pathlib import Path
from config import BUFFER_SIZE, SERVER_URL, SLEEP_TIME
from my_relais import Relay

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
    relay = Relay()

    relay.ON_1()
    # Initialize multiprocess logger
    my_logger.configure(Path("log.txt"), logging.DEBUG)
    my_logger.start()

    logger_main_process = my_logger.get_logger("mainprozess")
    logger_server_process = my_logger.get_logger("serverprozess")

    # logger_main_process.info("Thread meldet: TEST 1")
    # logger_main_process.error("Thread meldet: TEST 2")
    # Sepzifische Server Events
    handler_os_event_connect_server = MyEvent()
    handler_os_event_disconnect_server = MyEvent()
    handler_os_event_message_server = MyEvent()
    handler_os_event_alarm_server = MyEvent()
    handler_os_event_shutdown_server: MyEvent = MyEvent()
    handler_os_event_heartbeat_server: MyEvent = MyEvent()

    server_events : ServerEvents = ServerEvents()

    # Speichert Referenzen auf die Prozessklassen (könnten auch direkt übergeben werden)
    #handler_os_server : ServerProcess = ServerProcess(log_queue=log_queue,events = server_events, name="server",url=SERVER_URL)

    # Initialisiert Zeitstempel für die Heartbeat-Überwachung
    last_heartbeat: float = time.time()

    server_process = BaseProcess(logger=logger_server_process, name="Server", url=SERVER_URL, events=server_events)
    server_process.start()

    while True:
        try:
            now = time.time()
            # Prüft alle HEARTBEAT_INTERVAL Sekunden die Heartbeats der Prozesse
            if now - last_heartbeat >= HEARTBEAT_INTERVAL:
                for failed_process in check_all_heartbeats():
                    logger_main_process.critical(
                        f"{failed_process} hearbeat failed")
                    relay.OFF_1()
                last_heartbeat = now
        except Exception as e:
            logger_main_process.debug(f"Critical process error")
            server_process.terminate()
            relay.OFF_1()
            break
        # finally:
        #     # Kurzes Sleep, um CPU-Last zu minimieren und Tastendruck zuverlässig zu erkennen
        #     time.sleep(3)
        #     server_events.shutdown.set()
        #     break
    relay.OFF_1
    # Wartet auf das Ende aller Prozesse, bevor das Programm beendet wird
    for process in ProcessManager.processes.values():
        process.join()

    my_logger.stop()
     
