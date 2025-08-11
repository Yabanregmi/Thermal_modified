from typing import Any
import multiprocessing

from logging import Logger
from tb_events import ServerEvents
from tb_queues import SystemQueues
import time
from models.tb_dataclasses import QueuesMembers, SocketEventsFromBackend, SocketEventsToBackend, SocketMessage, QueueMessage, QueueTestEvents
from typing import Callable, Any

MAXIMUM_TIMEOUT: int = 10
HandlerType = Callable[..., None]
from tb_socket import Tb_Socket

class Tb_ServerProcess(multiprocessing.Process):
    """
    Basisklasse für alle Prozesse im System, die mit dem Server kommunizieren.
    """
    def __init__(self, name: str, logger: Logger, url: str, events: ServerEvents, queues : SystemQueues) -> None:
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
        self._validate_str(value=name, name="Name", min_len=3, max_len=50)
        self._validate_str(value=url, name="URL", min_len=5, max_len=200)

        super().__init__(name=name)
        self.logger :Logger= logger
        self.url :str= url
        self.events : ServerEvents = events
        
        self.queues : SystemQueues = queues

        self.in_konfig_modus: bool = False
        self.is_connected: bool = False
        self.is_connected_error : bool = False

        self.events_backend = [
            "ack_config", "ack_tempreture", "timeout_stop_record",
            "send_live_tempreture", "ack_call_live_tempreture",
            "ack_send_live_tempreture"
        ]

        self.sio : Tb_Socket = Tb_Socket(logger=self.logger)
        self.sio.register_event_handler(SocketEventsFromBackend.CONNECT, self.connect_handler)
        self.sio.register_event_handler(SocketEventsFromBackend.DISCONNECT, self.disconnect_handler)
        self.sio.register_event_handler(SocketEventsFromBackend.CONNECT_ERROR, self.connect_error_handler)
        self.sio.register_event_handler(SocketEventsFromBackend.REQ_RESET_ALARM, self.reset_alarm_handler)
        self.sio.register_event_handler(SocketEventsFromBackend.REQ_RESET_ERROR, self.reset_error_handler)
        self.sio.register_event_handler(SocketEventsFromBackend.REQ_SET_CONFIG, self.set_config_handler)
        self.sio.register_event_handler(SocketEventsFromBackend.REQ_SET_TEMPRETURE, self.set_tempreture_handler)
        self.sio.register_event_handler(SocketEventsFromBackend.REQ_MANUAL_START_RECORD, self.manual_start_record_handler)
        self.sio.register_event_handler(SocketEventsFromBackend.REQ_MANUAL_STOP_RECORD, self.manual_stop_record_handler)
        self.sio.register_event_handler(SocketEventsFromBackend.REQ_MANUAL_CALL_RECORD, self.manual_call_record_handler)
        self.sio.register_event_handler(SocketEventsFromBackend.REQ_CALL_LIVE_TEMPRETURE, self.call_live_tempreture_handler)
        self.sio.register_event_handler(SocketEventsFromBackend.REQ_CALL_HISTORY_TEMPRETURE, self.call_history_tempreture_handler)
        self.sio.register_event_handler(SocketEventsFromBackend.MESSAGE, self.message_handler)

        self.logger.debug(f"{self.__class__.__name__} - {self.name} init")
    # ------------------- Hilfsfunktion -------------------

    @staticmethod
    def _validate_str(value: str, name: str, min_len: int, max_len: int) -> None:
        if not (min_len <= len(value) <= max_len):
            raise ValueError(f"{name} muss zwischen {min_len} und {max_len} Zeichen lang sein.")
        
    # Event-Handler
    def connect_handler(self) -> None:
        self.is_connected = True
        self.is_connected_error = False
        self.events.connect.set()
        self.logger.debug(f"Verbindung url: {self.url} protocol: {self.sio.wrapper_transport()} sid: {self.sio.wrapper_get_sid()} erfolgreich!")

    def disconnect_handler(self) -> None:
        self.is_connected = False
        self.events.disconnect.set()
        self.logger.debug(f"Verbindung zu {self.url} beendet!")

    def connect_error_handler(self, data: Any) -> None:
        self.is_connected = False
        self.events.error_on_connection.set()
        if not self.is_connected_error:
            self.logger.warning(f"Connection error: {data}")
            self.is_connected_error = True

    def reset_alarm_handler(self) -> None:
        self.logger.warning("reset alarm")

    def reset_error_handler(self) -> None:
        self.logger.warning("reset error")

    def set_config_handler(self) -> None:
        self.logger.warning("set config")

    def set_tempreture_handler(self, data: Any) -> None:
        self.logger.warning(f"set tempreture {data}")

    def manual_start_record_handler(self) -> None:
        self.logger.warning("manual start record")

    def manual_stop_record_handler(self) -> None:
        self.logger.warning("manual stop record")

    def manual_call_record_handler(self) -> None:
        self.logger.warning("manual call record")

    def call_live_tempreture_handler(self) -> None:
        self.logger.warning("call live tempreture")

    def call_history_tempreture_handler(self) -> None:
        self.logger.warning("call history tempreture")

    def message_handler(self, data: Any) -> None:
        self.events.message.set()

    # Backend-Sende-Methoden
    def ack_config(self) -> None:
        msg : SocketMessage = SocketMessage(event=SocketEventsToBackend.ACK_SET_CONFIG, data="")
        self.sio.send_event(msg=msg,callback=self.ack_config_callback)

    def ack_tempreture(self,data:str) -> None:
        msg : SocketMessage = SocketMessage(event=SocketEventsToBackend.ACK_SET_TEMPRETURE, data=data)
        self.sio.send_event(msg=msg,callback=self.ack_tempreture_callback)

    def timeout_stop_record(self) -> None:
        msg : SocketMessage = SocketMessage(event=SocketEventsToBackend.ACK_MANUAL_STOP_RECORD, data="")
        self.sio.send_event(msg=msg,callback=self.timeout_stop_record_callback)

    def ack_call_live_tempreture(self) -> None:
        msg : SocketMessage = SocketMessage(event=SocketEventsToBackend.ACK_CALL_LIVE_TEMPRETURE, data="")
        self.sio.send_event(msg=msg,callback=self.ack_call_live_tempreture_callback)

    def ack_config_callback(self, response: Any = None) -> None:
        self.logger.debug(f"Callback ack_config empfangen mit response: {response}")

    def ack_tempreture_callback(self, response: Any = None) -> None:
        self.logger.debug(f"Callback ack_tempreture empfangen mit response: {response}")

    def timeout_stop_record_callback(self, response: Any = None) -> None:
        self.logger.debug(f"Callback timeout_stop_record empfangen mit response: {response}")

    def ack_call_live_tempreture_callback(self, response: Any = None) -> None:
        self.logger.debug(f"Callback ack_call_live_tempreture empfangen mit response: {response}")

    def ack_send_live_tempreture_callback(self, response: Any = None) -> None:
        self.logger.debug(f"Callback ack_send_live_tempreture empfangen mit response: {response}")

    def send_live_tempreture_callback(self, response: Any = None) -> None:
        self.logger.debug(f"Callback send_live_tempreture empfangen mit response: {response}")

    def shutdown(self):
        """
        Setzt das Shutdown-Event, um den Prozess zu beenden.
        """
        if not self.events.shutdown.is_set():
            self.events.shutdown.set()
            self.logger.debug(f"{self.__class__.__name__} - {self.name} called shutdown")

    def reset(self) -> bool:
        """
        Setzt den Prozess zurück und trennt die Verbindung.

        Returns:
            bool: True, wenn die Verbindung erfolgreich getrennt wurde, sonst False.
        """
        self.state : bool = True
        if self.is_connected :
            self.sio.wrapper_shutdown()
            self.sio.wrapper_disconnect()
            self.is_connected = False
            self.state = self.events.disconnect.wait(timeout=MAXIMUM_TIMEOUT)
        self.logger.debug(f"{self.__class__.__name__} - {self.name} reset")
        return self.state

    def send_to_backend(self, event:SocketEventsToBackend,data:str,callback: Callable[..., None]) -> None:
        res_msg = SocketMessage(event=event,data=data)
        self.sio.send_event(msg=res_msg,callback=self.ack_send_to_backend)
    
    def ack_send_to_backend(self) -> None:
        self.logger.debug("Message send to backend")

    def run(self) -> None:
        """
        Führt die Hauptlogik des Server-Prozesses aus.
        """
        self.logger.debug(f"{self.__class__.__name__} - {self.name} running")
        while not self.events.shutdown.is_set():
            if self.events.message.is_set():
                self.events.message.clear()
                self.send_to_backend(event=SocketEventsToBackend.ACK_MESSAGE,data="Hallo Peter", callback=self.ack_send_to_backend)

            if  self.events.error_on_connection.is_set():
                self.events.error_on_connection.clear()
                self.events.error_from_server_process.set()

            if not self.is_connected_error:
                if not self.events.server_process_okay.is_set():
                    self.events.server_process_okay.set()
        
            if not self.is_connected:
                try:
                    self.sio.wrapper_connect(self.url, transports=["websocket"])
                    self.is_connected = self.events.connect.wait(timeout=MAXIMUM_TIMEOUT)
                except Exception:
                    self.is_connected = False
        
            msg_in = self.queues.server.get()
            
            if not msg_in is None:
                if msg_in.source is QueuesMembers.MAIN and msg_in.dest is QueuesMembers.SERVER and msg_in.event is QueueTestEvents.REQ_FROM_MAIN_TO_SERVER:
                    if not self.queue_test_send_ack(req_msg=msg_in):
                        self.events.error_from_server_process.set()
                elif self.is_connected :
                    if msg_in.dest is QueuesMembers.BACKEND and msg_in.event in SocketEventsToBackend:
                        self.send_to_backend(event=SocketEventsToBackend(msg_in.event) ,data=msg_in.data, callback=self.ack_send_to_backend)
        
            self.events.heartbeat.set()
            time.sleep(0.1)
        
        if not self.reset():
            self.logger.debug(f"{self.__class__.__name__} - {self.name} shutdown error")
        else:
            self.logger.debug(f"{self.__class__.__name__} - {self.name} shutdown")
        
        if self.events.shutdown.is_set():
            self.events.shutdown.clear()
        time.sleep(1)
        
    def queue_test_send_ack(self, req_msg : QueueMessage) -> bool:
        status : bool = False
        try:
            if req_msg.event is QueueTestEvents.REQ_FROM_MAIN_TO_SERVER:
                res_msg : QueueMessage = QueueMessage(source=QueuesMembers.SERVER,dest=QueuesMembers.MAIN, event=QueueTestEvents.ACK_FROM_SERVER_TO_MAIN, data="")
                if not self.queues.main.put(item=res_msg):
                    status = False
                else:
                    status = True
        except Exception:
            status = False
        return status