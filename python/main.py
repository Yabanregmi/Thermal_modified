from dataclasses import dataclass
import logging
import time
from my_processes import (
    IrEvents,
    IrProcess,
    MyTimerThreadStartStop,
    TimerEvents,
    UserInputsEvents,
    UserInput,
    ProcessManager,
    ServerProcess,
    SystemQueues,
    ServerEvents,
)
from global_mp_logger import GlobalMPLogger as my_logger
from pathlib import Path
from config import SERVER_URL
from my_relais import Relay
from sys import exit
from queueTest import QueueTest, QueueTestEvents

timer_heartbeat_is_set_expired : bool = False
timer_queue_test_is_set_expired : bool = False

@dataclass
class Errors():
    internal_server : bool = False
    heartbeat_server : bool = False
    heartbeat_ir : bool = False
    ir: bool = False
    test_queues : bool = False
    
    def is_error(self) -> bool:
        status : bool = False
        if self.internal_server or self.heartbeat_server or self.ir or self.test_queues:
            status = True
        else:
            status = False
        return status
            

def shutdown_all_processes():
    for name in ProcessManager.processes:
        ProcessManager.shutdown_process(name=name)


def check_all_heartbeats() -> list[ServerProcess]:
    failed_processes: list[ServerProcess] = []

    for name in ProcessManager.processes:
        if not ProcessManager.check_heartbeat(name=name):
            failed_processes.append(ProcessManager.processes[name])

    return failed_processes

HEARTBEAT_INTERVAL = 3  # Sekunden: Intervall für Heartbeat-Überprüfung

def callback_timer_heartbeat():
    global timer_heartbeat_is_set_expired
    timer_heartbeat_is_set_expired = True
    
def init_logger():
    try:
        my_logger.configure(Path("log.txt"), logging.DEBUG)
        my_logger.start()
    except Exception as e:
        raise ValueError("Fehler beim Initialisieren des Loggers") from e
    
def init_server_process(queues : SystemQueues ,events: ServerEvents ) -> ServerProcess:
    try:
        logger_server = my_logger.get_logger("logger_server_process")
        server : ServerProcess = ServerProcess(name="server_process", logger=logger_server,  url=SERVER_URL, events=events, queues=queues)
        return server
    except Exception as e:
        raise ValueError("Fehler beim Initialisieren des Server-Prozesses") from e
    
def init_ir_process(queues : SystemQueues,events: IrEvents ) -> IrProcess:
    try:
        logger_ir = my_logger.get_logger("logger_ir_process")
        ir : IrProcess = IrProcess(name="ir_process",logger=logger_ir,events=events,queues=queues)
        return ir
    except Exception as e:
        raise ValueError("Fehler beim Initialisieren des Ir-Prozesses") from e
    
def init_system_queues() -> SystemQueues:
    try:
        logger_main = my_logger.get_logger("logger_queue_main")
        logger_server = my_logger.get_logger("logger_queue_server")
        logger_ir = my_logger.get_logger("logger_queue_ir")
        system_queues : SystemQueues = SystemQueues()
        system_queues.init(logger_main=logger_main, logger_server = logger_server, logger_ir=logger_ir)
        return system_queues
    except Exception as e:
        raise ValueError("Fehler beim Initialisieren der System Queues") from e

def init_timer_heartbeat(interval_s : int, events : TimerEvents)-> MyTimerThreadStartStop:
    try:
        if interval_s < 0:
            raise ValueError("Parameter-Fehler beim Initialisieren des Timer-Heartbeat")
        logger = my_logger.get_logger("logger_queue_main")
        thread_timer_heartbeat = MyTimerThreadStartStop(
        name="timer_heartbeat",logger=logger,interval_s = interval_s, 
        function= callback_timer_heartbeat, 
        events=events)
        return thread_timer_heartbeat
    except Exception as e:
        raise ValueError("Fehler beim Initialisieren des Timer-Heartbeat") from e

def init_user_input(events : UserInputsEvents)-> UserInput:
    try:
        logger = my_logger.get_logger("logger_user_input")
        thread : UserInput = UserInput(name="User_Input", logger = logger, events = events)
        return thread
    except Exception as e:
        raise ValueError("Fehler beim Initialisieren des User Inputs Thread") from e

def init_relais() -> Relay:
    logger = my_logger.get_logger("logger_relais")
    try:
        relay : Relay= Relay(logger=logger, bus_nr=1)
        return relay
    except Exception as e:
        raise ValueError("Fehler beim Initialisieren der Relais") from e

def init_queue_test(queues : SystemQueues, events : QueueTestEvents) -> QueueTest:
    try:
        logger_queue_test = my_logger.get_logger("logger_queue_test")
        logger_queue_test_timer = my_logger.get_logger("logger_queue_test_timer")
        test = QueueTest(logger=logger_queue_test, loggerTimer=logger_queue_test_timer,queues=queues, events=events)
        return test
    except Exception as e:
        raise ValueError("Fehler beim Initialisieren des Queue-Test") from e
    
def start_server_process(server : ServerProcess):
    try:
        if server == None:
            raise ValueError("Server start Fehler, Server ist nicht initialisiert")
        else:
            server.start()
    except Exception as e:
        raise ValueError("Fehler beim starten des Server Prozesses") from e
    
def start_ir_process(ir : IrProcess):
    try:
        if ir == None:
            raise ValueError("Ir start Fehler, Ir ist nicht initialisiert")
        else:
            ir.start()
    except Exception as e:
        raise ValueError("Fehler beim starten des Ir Prozesses") from e

def start_timer_heartbeat(timer : MyTimerThreadStartStop):
    try:
        if timer == None:
            raise ValueError("Ir start Fehler, Ir ist nicht initialisiert")
        else:
            timer.start()
    except Exception as e:
        raise ValueError("Fehler beim starten des Timer-Heartbeat") from e

def start_user_input(thread : UserInput):
    try:
        if thread == None:
            raise ValueError("Ir start Fehler, Ir ist nicht initialisiert")
        else:
            thread.start()
    except Exception as e:
        raise ValueError("Fehler beim starten des User-Input") from e
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
    
    loop_forever : bool = False
    init_error : bool = False
    errors = None 
    
    events_server = None 
    events_ir  = None 
    events_timer_heartbeat = None 
    events_user_input  = None 
    events_queue_test  = None 

    # Logger initialisieren
    system_queues = None 
    server_process = None 
    ir_process = None 
    thread_timer_heartbeat = None
    thread_user_input = None
    queue_test = None
    relays = None
    
    logger_main = None
    try:
        init_logger()
        logger_main = my_logger.get_logger("logger_main_process")
    except Exception:
        init_error = True
        
    if not init_error and not logger_main == None:
        try:
            errors = Errors()
            events_server = ServerEvents()
            events_ir = IrEvents()
            events_timer_heartbeat = TimerEvents()
            events_user_input = UserInputsEvents()
            events_queue_test = QueueTestEvents()
        
            system_queues = init_system_queues()
            server_process = init_server_process(queues=system_queues,events=events_server )
            ir_process = init_ir_process(events = events_ir, queues=system_queues)
            thread_timer_heartbeat = init_timer_heartbeat(3, events=events_timer_heartbeat)
            thread_user_input = init_user_input(events=events_user_input)
            
            relays = init_relais()
            queue_test = init_queue_test(queues=system_queues,events = events_queue_test)
        
            start_server_process(server=server_process)
            start_ir_process(ir=ir_process)
            start_timer_heartbeat(timer=thread_timer_heartbeat)
            start_user_input(thread=thread_user_input)
            loop_forever = True
            
            while loop_forever:
                    try:
                        queue_test.run()
                        if events_queue_test.test_done.wait(timeout=0):
                            if queue_test.is_error():
                                errors.test_queues = True
                                logger_main.critical(f"{__name__} QueueTest Fehlgeschlagen")
                            else:
                                logger_main.debug("QueueTest done")
                                
                        # Error handling - Server process 
                        if events_server.error_from_server_process.is_set():
                            errors.internal_server = True
                            events_server.error_from_server_process.clear()
                        elif events_server.server_process_okay.is_set():
                            errors.internal_server = False
                            events_server.server_process_okay.clear()

                        # Heartbeat handling - Server process
                        if timer_heartbeat_is_set_expired:
                            timer_heartbeat_is_set_expired = False

                            if not events_server.heartbeat.is_set():
                                errors.heartbeat_server = True
                                logger_main.critical(f"Server heartbeat failed")
                            
                            if not events_ir.heartbeat.is_set():
                                errors.heartbeat_ir = True
                                logger_main.critical(f"Ir heartbeat failed")
                            
                            if events_server.heartbeat.is_set() and events_ir.heartbeat.is_set():
                                events_server.heartbeat.clear()
                                events_ir.heartbeat.clear()
                                errors.heartbeat_server = False
                                errors.heartbeat_ir = False
                            thread_timer_heartbeat.restart()
                    except Exception as e:
                        logger_main.critical(f"Critical process error: {e}", exc_info=True)
                        server_process.terminate()

                    finally:
                        if errors.is_error():
                            relays.off_1()
                        else:
                            relays.on_1()
                            
                        if events_user_input.aborted.is_set():
                            events_user_input.aborted.clear()
                            loop_forever = False
                        time.sleep(1)
        except Exception as e:
            logger_main.error(f"Fehler bei der Prozessinitialisierung: {e}", exc_info=True)
            
    if not relays == None:
        relays.off_1()

    if not queue_test == None:
        queue_test.shutdown()
        queue_test.join()

    if not system_queues == None: 
        system_queues.main.shutdown()       
        system_queues.main.join()
        system_queues.server.shutdown()  
        system_queues.server.join()
        system_queues.ir.shutdown()  
        system_queues.ir.join()

    if not thread_user_input == None: 
        thread_user_input.shutdown()
        thread_user_input.join()
    
    if not thread_timer_heartbeat == None: 
        thread_timer_heartbeat.shutdown()
        thread_timer_heartbeat.join()
    
    if not ir_process == None:
        ir_process.shutdown()
        ir_process.join()
        
    if not server_process == None:
        server_process.shutdown()
        server_process.join()   

    if not logger_main == None:
        logger_main.debug("App stop")
    time.sleep(1)
    my_logger.stop()
    time.sleep(1)
                
if __name__ == "__main__":
    try:
        main()
        exit(0)
    except Exception as e:
        exit(1)
        

    