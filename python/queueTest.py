from dataclasses import dataclass, field
from math import e
from queue import Full
from my_processes import (
    TimerEvents,
    MyEvent,
    MyTimerThreadStartStop,
    QueueMessage,
    SystemQueues,
)
from time import time 
import messages

@dataclass
class QueueTestEvents():
    """
    Sammlung von Events zur Steuerung und Überwachung des Server-Prozesses.
    """
    name : str = "QueueTest"
    test_done: MyEvent = MyEvent(name = f"{name} test_done")
    shutdown : MyEvent = MyEvent(name = f"{name} shutdown")

@dataclass
class QueueTestFlags():
    set : bool = False
    done : bool  = False
    error : bool  = False

class QueueTest(): 
    def __init__(self, logger, loggerTimer, queues : SystemQueues, events : QueueTestEvents):

        self.is_init : bool = True
        self.test_server : QueueTestFlags = QueueTestFlags()
        self.test_main : QueueTestFlags = QueueTestFlags()
        self.test_ir : QueueTestFlags = QueueTestFlags()

        self.logger = logger
        
        self.queues = queues
        
        self.is_started : bool = False      
        self.set_test_msg_done : bool = False
        self.timer_expired : bool = False
        
        self.events : QueueTestEvents = events
        self.events_timer : TimerEvents = TimerEvents(name="Queue test timer")
        self.timer : MyTimerThreadStartStop = MyTimerThreadStartStop(
            name="timer_queue_test", logger=loggerTimer, interval_s = 10, 
            function= self._callback_timer_test, 
            events=self.events_timer )
        self.logger.debug("QueueTest init")

    def is_error(self) -> bool:
        status : bool = False
        if self.test_main.error or self.test_server.error or self.test_ir.error:
            status = True
        else:
            status = False
        return status

    def _clear_errors(self) -> None:
        self.test_main.error = False
        self.test_server.error = False
        self.test_ir.error = False
        
    def run(self):
        if not self.is_started :
            try :
                self.timer.start()   
                self.is_started = True       
            except Exception as e:
                self.is_started = False
                self.logger.debug("QueueTest - timer error")
        else :
            if not self.set_test_msg_done:
                self._set_test_msg()
                
                if not self.is_error():
                    self.set_test_msg_done = True
                else:
                    self._clear_errors()
            else:
                self._get_test_msg() 
            
        if self.timer_expired and self.is_started:
            self.set_test_msg_done = False
            
            if not self.test_main.done: 
                self.logger.debug("QueueTest - main - no ack - error")
                self.test_main.error = True
            else:
                self.test_main.done = False
                self.test_main.error = False
                
            if not self.test_server.done:
                self.logger.debug("QueueTest - server - no ack  - error")
                self.test_server.error = True
            else:
                self.test_server.done = False
                self.test_server.error = False
                
            if not self.test_ir.done:
                self.logger.debug("QueueTest - ir - no ack  - error")
                self.test_ir.error = True
            else:
                self.test_ir.done = False
                self.test_ir.error = False
                
            self.timer.restart()
            self.timer_expired = False
            self.events.test_done.set()
                                     
    def _callback_timer_test(self):
        self.timer_expired = True    

    def _set_test_msg(self):
        msg_main_req : QueueMessage = QueueMessage(command=messages.MSG_QUEUE_TEST_MAIN_REQ,timestamp=time(),data=messages.MSG_QUEUE_TEST_MAIN_REQ)

        if not self.queues.main.put(item=msg_main_req):
            self.logger.debug("Queue-Main-Test: Main-Queue voll.")
            self.test_main.error = True
            
        msg_server_req : QueueMessage = QueueMessage(command=messages.MSG_QUEUE_TEST_SERVER_REQ,timestamp=time(),data=messages.MSG_QUEUE_TEST_SERVER_REQ)
        
        if not self.queues.server.put(item=msg_server_req):
            self.logger.debug("Queue-Server-Test: Server-Queue voll.")
            self.test_server.error = True
                   
        msg_ir_req : QueueMessage = QueueMessage(command=messages.MSG_QUEUE_TEST_IR_REQ,timestamp=time(),data=messages.MSG_QUEUE_TEST_IR_REQ)

        if not self.queues.ir.put(item=msg_ir_req):
            self.logger.debug("Queue-Ir-Test: Ir-Queue voll.")
            self.test_ir.error = True   
             
    def _get_test_msg(self):
        msg = self.queues.main.get()
        
        if msg is not None:
            if msg.command == messages.MSG_QUEUE_TEST_MAIN_REQ:
                self.test_main.done = True
                self.test_main.set = False
            elif msg.command == messages.MSG_QUEUE_TEST_SERVER_ACK:
                self.test_server.done = True
                self.test_server.set = False
            elif msg.command == messages.MSG_QUEUE_TEST_IR_ACK:
                self.test_ir.done = True
                self.test_ir.set = False
            else:
                self.logger.debug(f"Error {self.__class__} - {msg.command}")
                
    def shutdown(self):
        self.logger.debug("QueueTest - shutdown")
        self.timer_expired = False
        self.timer.shutdown()

    def join(self):
        self.timer.join()
        self.logger.debug("QueueTest - Timer join")
        self.is_started = False
        self.set_test_msg_done = False

