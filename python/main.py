import logging
import time
from my_processes import (
    ProcessManager,
    ServerProcess
)
from global_mp_logger import GlobalMPLogger as my_logger
from my_processes import ServerEvents, MyEvent, MyTimerThread, user_input
from pathlib import Path
from config import SERVER_URL
from my_relais import Relay
from threading import Thread
from sys import exit

timer_heartbeat_is_set_expired : bool = False

def shutdown_all_processes():
    for name in ProcessManager.processes:
        ProcessManager.shutdown_process(name=name)


def check_all_heartbeats() -> list[ServerProcess]:
    failed_processes: list[ServerProcess] = []

    for name in ProcessManager.processes:
        if not ProcessManager.check_heartbeat(name=name):
            failed_processes.append(ProcessManager.processes[name])

    return failed_processes

def critical_error_loop(logger):
    """Endlosschleife im kritischen Fehlerfall – nur durch Neustart zu beenden."""
    logger.critical("Kritischer Fehler: Programm befindet sich in Fehler-Endlosschleife. Neustart erforderlich!")
    Relay.off_1()
    while True:
        time.sleep(10)  # CPU schonen, aber Zustand beibehalten


HEARTBEAT_INTERVAL = 3  # Sekunden: Intervall für Heartbeat-Überprüfung

def check_heartbeat():
    global timer_heartbeat_is_set_expired
    timer_heartbeat_is_set_expired = True
    
"""
main.py
--------
Startpunkt der Anwendung:
- Initialisiert und verwaltet alle Prozesse (Server, IO, DB)
- Sorgt für zentrales Logging
- Überwacht Heartbeats der Subprozesse im eingestellten Intervall
- Führt einen sauberen Shutdown aller Prozesse per Tastendruck ('q') durch
"""
def main ():
    global timer_heartbeat_is_set_expired
    loop_forever : bool = True
    events_server: ServerEvents = ServerEvents()
    event_timer_heartbeat_shutdown : MyEvent = MyEvent()
    event_user_input_shutdown : MyEvent = MyEvent()
    event_user_aborted : MyEvent = MyEvent()
    # Logger initialisieren
    my_logger.configure(Path("log.txt"), logging.DEBUG)
    my_logger.start()

    logger_main_process = my_logger.get_logger("mainprozess")
    logger_server_process = my_logger.get_logger("serverprozess")
    logger_relais = my_logger.get_logger("relais")
    logger_timer_heartbeat = my_logger.get_logger("timer_heartbeart")
    logger_user_input = my_logger.get_logger("user_input")

    Relay.init(logger=logger_relais, bus_nr=1)
    Relay.on_1()

    server_process = ServerProcess(logger=logger_server_process, name="Server", url=SERVER_URL, events=events_server)
    thread_timer_check_heartbeat = MyTimerThread(name="timer_heartbeart",logger=logger_timer_heartbeat,interval_s = 3, function= check_heartbeat, shutdown=event_timer_heartbeat_shutdown)
    thread_user_input = user_input(logger = logger_user_input,aborted=event_user_aborted, shutdown = event_user_input_shutdown)

    list_of_threads_and_processes = [
        server_process, 
        thread_timer_check_heartbeat, 
        thread_user_input]

    for i in list_of_threads_and_processes:
        if hasattr(i, "start"):
            i.start()
        else:
            loop_forever = False
        time.sleep(0.2)

    while loop_forever:
        try:
            # Error handling - Server process 
            if events_server.error_from_server_process.is_set():
                Relay.on_3()
                events_server.error_from_server_process.clear()

            if events_server.server_process_okay.is_set():
                Relay.off_3()
                events_server.server_process_okay.clear()

            # Heartbeat handling - Server process
            if timer_heartbeat_is_set_expired:
                timer_heartbeat_is_set_expired = False

                if not events_server.heartbeat.is_set():
                    logger_main_process.critical(f"Server heartbeat failed")
                    Relay.off_1()
                else:
                    events_server.heartbeat.clear()

                thread_timer_check_heartbeat.restart()

            time.sleep(0.1)
        except Exception as e:
            logger_main_process.critical(f"Critical process error: {e}", exc_info=True)
            server_process.terminate()
            # Keine break-Anweisung mehr, sondern in Fehler-Endlosschleife springen:
            critical_error_loop(logger_main_process)
        finally:
            if event_user_aborted.is_set():
                Relay.off_1()
                for i in list_of_threads_and_processes:
                    if hasattr(i, "is_alive") and i.is_alive():
                        if hasattr(i, "shutdown"):
                            i.shutdown()
                        i.join()
                logger_main_process.debug("App stop")
                time.sleep(1)
                my_logger.stop()
                loop_forever = False

if __name__ == "__main__":
    try:
        main()
        exit(0)
    except Exception as e:
        exit(1)