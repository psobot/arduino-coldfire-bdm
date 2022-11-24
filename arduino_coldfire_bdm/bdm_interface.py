import time
import random
from typing import List, Iterable
from arduino_coldfire_bdm.serial_interface import ColdfireSerialInterface


NUM_ADDRESS_REGISTERS = 8
NUM_DATA_REGISTERS = 8


def format_hex_list(values: List[int]) -> str:
    return f"[{', '.join([f'0x{v:08x}' for v in values])}]"


class ConfigurationStatusRegister:
    def __init__(self, data: int):
        self.data = data

    def __repr__(self) -> str:
        return f"<CSR data=0x{self.data:08x} single_step_mode={self.single_step_mode}>"

    @property
    def single_step_mode(self) -> bool:
        return bool((self.data >> 4) & 0x1)


class BDMCommandInterface:
    """
    A wrapper around a ColdfireSerialInterface that provides
    BDM (Background Debug Mode) commands.
    """

    def __init__(self, interface: ColdfireSerialInterface):
        self.interface = interface
        self.current_step_mode = False

    def _send(self, *commands):
        """
        Send one or more 16-bit packets (`commands`) while receiving (and discarding) any
        responses from previously-sent commands. This method will still throw exceptions
        if any of the previous commands failed.
        """
        for command in commands:
            self.interface.send_and_receive_packet(command)

    def _send_then_receive(self, *commands, response_size_words: int = 1) -> int:
        """
        Send one or more 16-bit packets (`commands`) then receive `response_size_words` words.
        Returns a single integer, which is the response data.
        """
        for command in commands:
            self.interface.send_and_receive_packet(command)
        responses = [self.interface.receive_packet() for _ in range(response_size_words)]
        response_data = responses[0].data
        if len(responses) == 2:
            response_data <<= 16
            response_data |= responses[1].data
        return response_data

    def noop(self):
        """
        Perform no operation; may be used as a null command.
        """
        return self._send_then_receive(0x0000)

    def go(self):
        """
        Resume execution from the current program counter.
        Execution proceeds forward without single-step mode;
        this is the equivalent of GDB/LLDB's "continue" command.
        """
        self.set_single_step_mode(False)
        return self._send_then_receive(0x0C00)

    def step(self):
        """
        Resume execution from the current program counter, stopping
        after the next instruction has been executed. This is the
        equivalent of GDB/LLDB's "step" command.
        """
        self.set_single_step_mode(True)
        return self._send_then_receive(0x0C00)

    def read_byte(self, address: int) -> int:
        """
        Read a single byte from the provided memory address.
        """
        return self._send_then_receive(0x1900, address >> 16, address & 0xFFFF) & 0xFF

    def read_word(self, address: int) -> int:
        """
        Read a single word (16 bits) from the provided memory address.
        """
        return self._send_then_receive(0x1940, address >> 16, address & 0xFFFF)

    def read_longword(self, address: int) -> int:
        """
        Read a longword (32 bits) from the provided memory address.
        """
        return self._send_then_receive(
            0x1980, address >> 16, address & 0xFFFF, response_size_words=2
        )

    def read_address_register(self, register_number: int) -> int:
        """
        Read the 32-bit contents of the given address register.
        """
        if register_number > (NUM_ADDRESS_REGISTERS - 1) or register_number < 0:
            raise ValueError(
                f"Can't read register {register_number:,} - Coldfire only has"
                f" {NUM_ADDRESS_REGISTERS} address registers!"
            )
        return self._send_then_receive(0x2188 | register_number, response_size_words=2)

    def read_data_register(self, register_number) -> int:
        """
        Read the 32-bit contents of the given data register.
        """
        if register_number > (NUM_DATA_REGISTERS - 1) or register_number < 0:
            raise ValueError(
                f"Can't read register {register_number:,} - Coldfire only has"
                f" {NUM_DATA_REGISTERS} data registers!"
            )
        return self._send_then_receive(0x2180 | register_number, response_size_words=2)

    def read_control_register(self, register_encoding: int) -> int:
        """
        Read the contents of one of the system control registers.
        See the Coldfire manual for these control registers.
        """
        if register_encoding < 0 or register_encoding > 4095:
            raise ValueError("Coldfire only has a 12-bit control register field!")
        return self._send_then_receive(0x2980, 0, register_encoding & 0xFFF, response_size_words=2)

    def read_debug_configuration_status_register(self) -> ConfigurationStatusRegister:
        """
        Read the contents of the Configuration Status Register (CSR) used for debugging.
        This register stores data including (but not limited to) the processor step mode,
        useful for stepping through instruction-by-instruction.
        """
        return ConfigurationStatusRegister(self._send_then_receive(0x2D80, response_size_words=2))

    def write_debug_configuration_status_register(self, new_value: int):
        """
        Write the contents of the Configuration Status Register (CSR) used for debugging.
        This register stores data including (but not limited to) the processor step mode,
        useful for stepping through instruction-by-instruction.
        """
        return self._send_then_receive(0x2C80, new_value >> 16, new_value & 0xFFF)

    def set_single_step_mode(self, enabled=True):
        """
        Set the processor's single-step mode to the provided value.
        This controls the execution of the processor between instructions; if enabled,
        the processor will halt after every instruction, allowing debugging of the system.
        """
        if self.current_step_mode == enabled:
            return
        csr = self.read_debug_configuration_status_register()
        new_register = csr.data
        new_register &= 0xFFFFFFEF
        if enabled:
            new_register |= 0b10000
        self.write_debug_configuration_status_register(new_register)
        self.current_step_mode = enabled

    def dump_words(self, base_address: int, num_words: int) -> Iterable[int]:
        """
        Dump successive 16-bit words from the provided base address in an efficient manner.
        This is about three times faster than reading individual words, as the address of
        each word does not need to be specified.
        """
        self.interface.send_packet(0x1940)
        self.interface.send_packet(base_address >> 16)
        self.interface.send_packet(base_address & 0xFFFF)
        num_words -= 1
        for _ in range(num_words):
            yield self.interface.send_and_receive_packet(0x1D40).data
        yield self.interface.receive_packet().data

    def write_byte(self, address: int, data: int):
        """
        Write the provided byte to the provided address in memory.
        """
        if data > 255 or data < 0:
            raise ValueError("Cannot write byte out of range for byte!")
        return self._send(0x1800, address >> 16, address & 0xFFFF, data & 0xFF)

    def write_word(self, address: int, data: int):
        """
        Write the provided 16-bit word to the provided address in memory.
        """
        if data > 0xFFFF or data < 0:
            raise ValueError("Cannot write byte out of range for word!")
        return self._send(0x1840, address >> 16, address & 0xFFFF, data)

    def write_longword(self, address: int, data: int):
        """
        Write the provided 32-bit longword to the provided address in memory.
        """
        return self._send(0x1880, address >> 16, address & 0xFFFF, data >> 16, data & 0xFFFF)

    def write_control_register(self, register: int, data: int):
        """
        Write the provided 32-bit longword to the provided control register.
        """
        return self._send(0x2880, 0, register & 0xFFFF, data >> 16, data & 0xFFFF)

    def write_address_register(self, register_number: int, data: int):
        """
        Write the provided 32-bit longword to the provided address register.
        """
        if register_number > (NUM_ADDRESS_REGISTERS - 1) or register_number < 0:
            raise ValueError(
                f"Can't write register {register_number:,} - Coldfire only has"
                f" {NUM_ADDRESS_REGISTERS} address registers!"
            )
        return self._send_then_receive(0x2088 | register_number)

    def write_data_register(self, register_number: int, data: int):
        """
        Write the provided 32-bit longword to the provided data register.
        """
        if register_number > (NUM_DATA_REGISTERS - 1) or register_number < 0:
            raise ValueError(
                f"Can't write register {register_number:,} - Coldfire only has"
                f" {NUM_DATA_REGISTERS} data registers!"
            )
        return self._send_then_receive(0x2080 | register_number)

    def send_flash_write_enable(self):
        """
        If the attached system has a Flash boot ROM mapped at 0x00000000,
        this command unlocks that Flash chip for writing. The next write
        (using `write_byte`, `write_word`, or `write_longword`) will succeed.

        Note that when writing Flash memory, `0` bits can not be programmed
        to the value `1`; an entire flash chip erase may be necessary first
        to initialize all bits to `1` first.
        """
        # This is the flash programming unlock sequence for a single word of memory,
        # assuming a word-addressable Flash memory attached at as Boot ROM.
        self.write_word(0x555 << 1, 0xAA)
        self.write_word(0x2AA << 1, 0x55)
        self.write_word(0x555 << 1, 0xA0)

    def enter_flash_unlock_bypass(self):
        """
        If the attached system has a Flash boot ROM mapped at 0x00000000,
        this command puts that Flash chip into "unlock bypass mode,"
        enabling faster writes by sending only a pair of words per
        word written. This command must be paired with
        `exit_flash_unlock_bypass` when the writes are complete.
        """
        self.write_word(0x555 << 1, 0xAA)
        self.write_word(0x2AA << 1, 0x55)
        self.write_word(0x555 << 1, 0x20)
        self.in_unlock_bypass_mode = True

    def send_unlock_bypassed_flash_write(self, address: int, data: int):
        """
        If the attached system has a Flash boot ROM mapped at 0x00000000,
        and `enter_flash_unlock_bypass` has been called,
        this command writes a single word to the Flash.

        Note that when writing Flash memory, `0` bits can not be programmed
        to the value `1`; an entire flash chip erase may be necessary first
        to initialize all bits to `1` first.
        """
        if not self.in_unlock_bypass_mode:
            raise RuntimeError(
                "To use this method, ensure that `enter_flash_unlock_bypass` has been called first."
            )
        self.write_word(0x00, 0xA0)
        self.write_word(address, data)

    def exit_flash_unlock_bypass(self):
        """
        If the attached system has a Flash boot ROM mapped at 0x00000000,
        this command tells that Flash chip to exit "unlock bypass mode,"
        returning to normal operation (that is: disallowing writes).
        """
        self.write_word(0x00, 0x90)
        self.write_word(0x00, 0x00)
        self.in_unlock_bypass_mode = False

    def send_flash_chip_erase(self):
        """
        Send the required commands to erase an entire attached flash chip.
        Note that this takes up to 30 seconds, and internally sleeps for that long.
        """
        self.write_word(0x555 << 1, 0xAA)
        self.write_word(0x2AA << 1, 0x55)
        self.write_word(0x555 << 1, 0x80)
        self.write_word(0x555 << 1, 0xAA)
        self.write_word(0x2AA << 1, 0x55)
        self.write_word(0x555 << 1, 0x10)
        # TODO: Read words from the attached Flash to figure out how long to wait for.
        time.sleep(30)
        self.write_word(0x555 << 1, 0xF0)

    def consistency_check(self):
        """
        Perform a consistency check on the attached Coldfire by reading and
        writing to all of the processor's registers, and ensuring that the
        values stick. This will raise a ValueError if any communication or
        consistency errors are detected.
        """
        address_contents = [self.read_address_register(i) for i in range(NUM_ADDRESS_REGISTERS)]
        data_contents = [self.read_data_register(i) for i in range(NUM_DATA_REGISTERS)]

        # Read the address and data registers again and ensure consistency:
        address_contents_again = [
            self.read_address_register(i) for i in range(NUM_ADDRESS_REGISTERS)
        ]
        if address_contents_again != address_contents:
            raise ValueError(
                f"Read all {NUM_ADDRESS_REGISTERS} address registers twice in a row, but found"
                " different results. This could indicate that the attached Coldfire processor is"
                " still running (i.e.: not halted), not properly connected to the debug port, or"
                " that the processor may be faulty. Inital values were:"
                f" {format_hex_list(address_contents)}, second read resulted in:"
                f" {format_hex_list(address_contents_again)}"
            )
        data_contents_again = [self.read_data_register(i) for i in range(NUM_DATA_REGISTERS)]
        if data_contents_again != data_contents:
            raise ValueError(
                f"Read all {NUM_DATA_REGISTERS} data registers twice in a row, but found different"
                " results. This could indicate that the attached Coldfire processor is still"
                " running (i.e.: not halted), not properly connected to the debug port, or that"
                " the processor may be faulty. Inital values were:"
                f" {format_hex_list(data_contents)}, second read resulted in:"
                f" {format_hex_list(data_contents_again)}"
            )

        # Write new random values to the address and data registers:
        expected_address_contents = [
            int(random.random() * 0xFFFFFFFF) for _ in range(NUM_ADDRESS_REGISTERS)
        ]
        expected_data_contents = [
            int(random.random() * 0xFFFFFFFF) for _ in range(NUM_DATA_REGISTERS)
        ]
        for i, value in enumerate(expected_address_contents):
            self.write_address_register(i, value)
        for i, value in enumerate(expected_data_contents):
            self.write_data_register(i, value)

        # Check to ensure that the values "stuck":
        address_contents_again = [
            self.read_address_register(i) for i in range(NUM_ADDRESS_REGISTERS)
        ]
        if address_contents_again != expected_address_contents:
            raise ValueError(
                f"Wrote to all {NUM_ADDRESS_REGISTERS} address registers, but read different"
                " results. This could indicate that the attached Coldfire processor is still"
                " running (i.e.: not halted), not properly connected to the debug port, or that"
                " the processor may be faulty. Written values were:"
                f" {format_hex_list(expected_address_contents)}, but read-back resulted in:"
                f" {format_hex_list(address_contents_again)}"
            )
        data_contents_again = [self.read_data_register(i) for i in range(NUM_DATA_REGISTERS)]
        if data_contents_again != expected_data_contents:
            raise ValueError(
                f"Wrote to all {NUM_DATA_REGISTERS} data registers twice in a row, but read"
                " different results. This could indicate that the attached Coldfire processor is"
                " still running (i.e.: not halted), not properly connected to the debug port, or"
                " that the processor may be faulty. Written values were:"
                f" {format_hex_list(expected_data_contents)}, but read-back resulted in:"
                f" {format_hex_list(data_contents_again)}"
            )

        # Write the original values back to the processor to be a nice person:
        for i, value in enumerate(address_contents):
            self.write_address_register(i, value)
        for i, value in enumerate(data_contents):
            self.write_data_register(i, value)
