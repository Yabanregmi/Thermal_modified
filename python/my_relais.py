import smbus2 as smbus
from typing import Any, Optional, List
from logging import Logger
class Relay:
    # Konstanten
    NUM_RELAY_PORTS: int = 4
    DEVICE_ADDRESS: int = 0x24
    DEVICE_CONFIGURATION_REGISTER: int = 0x06
    DEVICE_OUTPUT_PORT_REGISTER: int = 0x02
    DEVICE_SET_PINS_AS_OUTPUTS: int = 0x00
    DEVICE_DATA: int = 0x00

    # Statusflags (global für alle Relais im System!)
    relay_1_is_set: bool = False
    relay_2_is_set: bool = False
    relay_3_is_set: bool = False
    relay_4_is_set: bool = False

    # Logger und Bus (müssen vor Benutzung gesetzt werden)
    logger: Logger
    bus: smbus.SMBus
    
    relais_names : List[str] = ["","","",""]

    @classmethod
    def init(cls, logger: Any, bus_nr: int = 1, relais_names : List[str] = ["","","",""]) -> None:
        cls.logger : Logger = logger
        cls.bus : smbus.SMBus = smbus.SMBus(bus_nr)
        cls.logger.warning(f"ADR: {cls.DEVICE_ADDRESS}, Ports {cls.NUM_RELAY_PORTS}")
        cls._reset_register()
        
        
        if relais_names is not None and len(relais_names) > 4:
            cls.relais_names = relais_names
        else:
            cls.relais_names = ["Relais1","Relais2","Relais3","Relais4"]
        
        cls.all_off()

    @classmethod
    def _reset_register(cls) -> None:
        cls.logger.warning('Reset relay register')
        cls.bus.write_byte_data(cls.DEVICE_ADDRESS, cls.DEVICE_CONFIGURATION_REGISTER, cls.DEVICE_SET_PINS_AS_OUTPUTS)

    @classmethod
    def on_1(cls) -> None:
        if not cls.relay_1_is_set:
            cls._relay_on(relay_num=1, name=cls.relais_names[0])
            cls.relay_1_is_set = True

    @classmethod
    def on_2(cls) -> None:
        if not cls.relay_2_is_set:
            cls._relay_on(relay_num=2, name=cls.relais_names[1])
            cls.relay_2_is_set = True

    @classmethod
    def on_3(cls) -> None:
        if not cls.relay_3_is_set:
            cls._relay_on(relay_num=3, name=cls.relais_names[2])
            cls.relay_3_is_set = True

    @classmethod
    def on_4(cls) -> None:
        if not cls.relay_4_is_set:
            cls._relay_on(relay_num=4, name=cls.relais_names[3])
            cls.relay_4_is_set = True

    @classmethod
    def off_1(cls) -> None:
        if cls.relay_1_is_set:
            cls._relay_off(relay_num=1, name=cls.relais_names[0])
            cls.relay_1_is_set = False

    @classmethod
    def off_2(cls) -> None:
        if cls.relay_2_is_set:
            cls._relay_off(relay_num=2, name=cls.relais_names[1])
            cls.relay_2_is_set = False

    @classmethod
    def off_3(cls) -> None:
        if cls.relay_3_is_set:
            cls._relay_off(relay_num=3, name=cls.relais_names[2])
            cls.relay_3_is_set = False

    @classmethod
    def off_4(cls) -> None:
        if cls.relay_4_is_set:
            cls._relay_off(relay_num=4, name=cls.relais_names[3])
            cls.relay_4_is_set = False

    @classmethod
    def all_on(cls) -> None:
        cls.on_1()
        cls.on_2()
        cls.on_3()
        cls.on_4()

    @classmethod
    def all_off(cls) -> None:
        cls.off_1()
        cls.off_2()
        cls.off_3()
        cls.off_4()

    @classmethod
    def _relay_on(cls, relay_num: int, name : str) -> None:
        if 0 < relay_num <= cls.NUM_RELAY_PORTS:
            cls.logger.warning(f'Relay {name} ON')
            cls.DEVICE_DATA |= (0x1 << (relay_num - 1))
            cls.bus.write_byte_data(cls.DEVICE_ADDRESS, cls.DEVICE_OUTPUT_PORT_REGISTER, cls.DEVICE_DATA)
        else:
            cls.logger.warning(f'Invalid relay #: {name}')

    @classmethod
    def _relay_off(cls, relay_num: int, name : str) -> None:
        if 0 < relay_num <= cls.NUM_RELAY_PORTS:
            cls.logger.warning(f'Relay {name} OFF')
            cls.DEVICE_DATA &= ~(0x1 << (relay_num - 1))
            cls.bus.write_byte_data(cls.DEVICE_ADDRESS, cls.DEVICE_OUTPUT_PORT_REGISTER, cls.DEVICE_DATA)
        else:
            cls.logger.warning(f'Invalid relay #: {name}')

    @classmethod
    def relay_toggle_port(cls, relay_num: int, name : str) -> None:
        cls.logger.warning(f'Toggling relay: {name}')
        if cls.relay_get_port_status(relay_num):
            cls._relay_off(relay_num, name)
        else:
            cls._relay_on(relay_num, name)

    @classmethod
    def relay_get_port_status(cls, relay_num: int) -> bool:
        cls.logger.warning(f'Checking status of relay {relay_num}')
        res = cls.relay_get_port_data(relay_num)
        if res > 0:
            mask = 1 << (relay_num - 1)
            return (cls.DEVICE_DATA & mask) == 0
        else:
            cls.logger.warning("Specified relay port is invalid")
            return False
        
    @classmethod
    def relay_get_port_data(cls, relay_num: int) -> int:
        cls.logger.warning(f'Reading relay status value for relay {relay_num}')
        if 0 < relay_num <= cls.NUM_RELAY_PORTS:
            device_reg_data = cls.bus.read_byte_data(cls.DEVICE_ADDRESS, cls.DEVICE_OUTPUT_PORT_REGISTER)
            return device_reg_data
        else:
            cls.logger.warning("Specified relay port is invalid")
            return 0