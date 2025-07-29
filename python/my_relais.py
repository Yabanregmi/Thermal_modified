import smbus2 as smbus
from typing import Any, Optional
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

    @classmethod
    def init(cls, logger: Any, bus_nr: int = 1) -> None:
        cls.logger : Logger = logger
        cls.bus : smbus.SMBus = smbus.SMBus(bus_nr)
        cls.logger.debug(f"ADR: {cls.DEVICE_ADDRESS}, Ports {cls.NUM_RELAY_PORTS}")
        cls._reset_register()
        cls.all_off()

    @classmethod
    def _reset_register(cls) -> None:
        cls.logger.debug('Reset relay register')
        cls.bus.write_byte_data(cls.DEVICE_ADDRESS, cls.DEVICE_CONFIGURATION_REGISTER, cls.DEVICE_SET_PINS_AS_OUTPUTS)

    @classmethod
    def on_1(cls) -> None:
        if not cls.relay_1_is_set:
            cls._relay_on(1)
            cls.relay_1_is_set = True

    @classmethod
    def on_2(cls) -> None:
        if not cls.relay_2_is_set:
            cls._relay_on(2)
            cls.relay_2_is_set = True

    @classmethod
    def on_3(cls) -> None:
        if not cls.relay_3_is_set:
            cls._relay_on(3)
            cls.relay_3_is_set = True

    @classmethod
    def on_4(cls) -> None:
        if not cls.relay_4_is_set:
            cls._relay_on(4)
            cls.relay_4_is_set = True

    @classmethod
    def off_1(cls) -> None:
        if cls.relay_1_is_set:
            cls._relay_off(1)
            cls.relay_1_is_set = False

    @classmethod
    def off_2(cls) -> None:
        if cls.relay_2_is_set:
            cls._relay_off(2)
            cls.relay_2_is_set = False

    @classmethod
    def off_3(cls) -> None:
        if cls.relay_3_is_set:
            cls._relay_off(3)
            cls.relay_3_is_set = False

    @classmethod
    def off_4(cls) -> None:
        if cls.relay_4_is_set:
            cls._relay_off(4)
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
    def _relay_on(cls, relay_num: int) -> None:
        if 0 < relay_num <= cls.NUM_RELAY_PORTS:
            cls.logger.debug(f'Relay {relay_num} ON')
            cls.DEVICE_DATA |= (0x1 << (relay_num - 1))
            cls.bus.write_byte_data(cls.DEVICE_ADDRESS, cls.DEVICE_OUTPUT_PORT_REGISTER, cls.DEVICE_DATA)
        else:
            cls.logger.debug(f'Invalid relay #: {relay_num}')

    @classmethod
    def _relay_off(cls, relay_num: int) -> None:
        if 0 < relay_num <= cls.NUM_RELAY_PORTS:
            cls.logger.debug(f'Relay {relay_num} OFF')
            cls.DEVICE_DATA &= ~(0x1 << (relay_num - 1))
            cls.bus.write_byte_data(cls.DEVICE_ADDRESS, cls.DEVICE_OUTPUT_PORT_REGISTER, cls.DEVICE_DATA)
        else:
            cls.logger.debug(f'Invalid relay #: {relay_num}')

    @classmethod
    def relay_toggle_port(cls, relay_num: int) -> None:
        cls.logger.debug(f'Toggling relay: {relay_num}')
        if cls.relay_get_port_status(relay_num):
            cls._relay_off(relay_num)
        else:
            cls._relay_on(relay_num)

    @classmethod
    def relay_get_port_status(cls, relay_num: int) -> bool:
        cls.logger.debug(f'Checking status of relay {relay_num}')
        res = cls.relay_get_port_data(relay_num)
        if res > 0:
            mask = 1 << (relay_num - 1)
            return (cls.DEVICE_DATA & mask) == 0
        else:
            cls.logger.debug("Specified relay port is invalid")
            return False
        
    @classmethod
    def relay_get_port_data(cls, relay_num: int) -> int:
        cls.logger.debug(f'Reading relay status value for relay {relay_num}')
        if 0 < relay_num <= cls.NUM_RELAY_PORTS:
            device_reg_data = cls.bus.read_byte_data(cls.DEVICE_ADDRESS, cls.DEVICE_OUTPUT_PORT_REGISTER)
            return device_reg_data
        else:
            cls.logger.debug("Specified relay port is invalid")
            return 0