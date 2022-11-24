import sys
import argparse
from contextlib import nullcontext
import serial
import time
from tqdm import tqdm

from arduino_coldfire_bdm.serial_interface import (
    ColdfireSerialInterface,
    MockColdfireSerialInterface,
)
from arduino_coldfire_bdm.bdm_interface import BDMCommandInterface
from arduino_coldfire_bdm.control_registers import ControlRegisters


PADDR_OFFSET = 0x244
PADAT_OFFSET = 0x248


def dump_memory_to_ascii(
    bdm,
    ofile,
    base: int = 0x00200000,
    length_in_bytes: int = 0x100,
    words_per_line: int = 8,
    binary: bool = False,
):
    for i, word in enumerate(bdm.dump_words(base, length_in_bytes // 2)):
        try:
            address = base + (i * 2)
            if (address - base) % (words_per_line * 4) == 0:
                if address > base:
                    ofile.write("\n")
                ofile.write(f"0x{address:08x}: ")
            if binary:
                ofile.write(f"{word >> 8:08b} {word & 0xFF:08b} ")
            else:
                ofile.write(f"{word:04x}")
            if ((address - base) + 2) % 4 == 0:
                ofile.write(f" ")
        except KeyboardInterrupt:
            ofile.write("\n")
            break
    print()


def register_dump_command(subparsers):
    subparser = subparsers.add_parser("dump_memory", help="Dump memory.")
    subparser.add_argument(
        "--starting-address",
        type=lambda s: int(s, 0),
        default=0x0,
        help="The starting address to dump memory from.",
    )
    subparser.add_argument(
        "--num-bytes",
        type=lambda s: int(s, 0),
        default=0x1000000,
        help="The number of bytes to dump.",
    )
    subparser.add_argument("--output-format", choices=["xxd", "raw", "binary"])
    subparser.add_argument("--output-filename", default="stdout")

    def dump(args, bdm):
        if args.output_filename == "stdout":
            if args.output_format == "raw":
                ofile = sys.stdout.buffer
            else:
                ofile = sys.stdout
        else:
            if args.output_format == "raw":
                ofile = open(args.output_filename, "wb")
            else:
                ofile = open(args.output_filename, "w")
        if args.output_format == "raw":
            for word in bdm.dump_words(args.starting_address, args.num_bytes // 2):
                ofile.write((word >> 8).to_bytes(1, byteorder="big"))
                ofile.write((word & 0xFF).to_bytes(1, byteorder="big"))
        else:
            dump_memory_to_ascii(
                bdm,
                ofile,
                args.starting_address,
                args.num_bytes,
                binary=args.output_format == "binary",
            )

    subparser.set_defaults(func=dump)


def register_trace_command(subparsers):
    subparser = subparsers.add_parser(
        "trace_execution",
        help=(
            "Begin execution and print out the program counter and registers before every"
            " instruction."
        ),
    )
    subparser.add_argument(
        "--starting-address",
        type=lambda s: int(s, 0),
        help="The starting address to begin execution from.",
        default=0x400,
    )
    subparser.add_argument(
        "--num-instructions",
        type=lambda s: int(s, 0),
        default=0x10000000,
        help="The number of instructions to execute.",
    )
    subparser.add_argument(
        "--stop-on-zero",
        action="store_true",
        help=(
            "If passed, stop tracing if the program counter goes to 0x0 (probably indicating a"
            " crash or reset)."
        ),
    )

    def trace(args, bdm):
        print(f"Starting execution from 0x{args.starting_address:08x}...")
        bdm.write_control_register(ControlRegisters.PC, args.starting_address)

        print(
            "\t".join(
                ["PC        ", "SP        "]
                + [f"D{i}        " for i in range(4)]
                + [f"A{i}        " for i in range(4)]
                + ["MBAR      ", "PADDR     ", "PADAT     "]
            )
        )
        for _ in range(0, args.num_instructions):
            try:
                pc = bdm.read_control_register(ControlRegisters.PC)
                sp = bdm.read_address_register(7)
                data_registers = [bdm.read_data_register(i) for i in range(4)]
                address_registers = [bdm.read_address_register(i) for i in range(4)]
                mbar = bdm.read_control_register(ControlRegisters.MBAR)

                values = (
                    [pc, sp]
                    + data_registers
                    + address_registers
                    + [
                        mbar,
                        bdm.read_word((mbar & 0xFFFFFFFE) + PADDR_OFFSET),
                        bdm.read_word((mbar & 0xFFFFFFFE) + PADAT_OFFSET),
                    ]
                )
                print("\t".join([f"0x{v:08x}" for v in values]))
                if pc == 0x0 and args.stop_on_zero:
                    print(f"Program counter is 0; exiting, the processor has probably crashed.")
                    break
                bdm.step()
            except KeyboardInterrupt:
                break

    subparser.set_defaults(func=trace)


def register_load_command(subparsers):
    subparser = subparsers.add_parser(
        "load_flash",
        help="Erase an attached Flash chip and load in new contents from a file.",
    )
    subparser.add_argument("input_file", help="The path to the input file to load into memory.")
    subparser.add_argument(
        "--skip-erase",
        action="store_true",
        help=(
            "If passed, skip erasing the chip. This may result in an incorrect load if the Flash"
            " chip is not already filled with 0xFFFF."
        ),
    )
    subparser.add_argument(
        "--max-bytes",
        type=lambda s: int(s, 0),
        default=0x10000000,
        help=(
            "The maximum number of bytes to load from the provided filename. Must be a number"
            " divisible by two."
        ),
    )

    def load(args, bdm):
        start = time.time()
        with open(args.input_file, "rb") as f:
            data = f.read()
            print(f"Read {len(data):,} bytes from {args.input_file} to load into Flash.")
            if args.max_bytes < len(data):
                if args.max_bytes % 2 == 1:
                    raise ValueError(
                        f"--max-bytes {args.max_bytes} was passed, but the number of bytes to load"
                        " must be divisible by two."
                    )
                data = data[: args.max_bytes]
                print(f"Only loading the first {args.max_bytes:,} bytes.")

        if not args.skip_erase:
            print("Sending full chip erase...")
            bdm.send_flash_chip_erase()
            print("Testing that chip was erased...")
            words = [(i, bdm.read_word(i)) for i in range(0, 16, 2)]
            if not all([word == 0xFFFF for _, word in words]):
                raise RuntimeError(
                    "Flash chip was not erased! Expected all words to be 0xFFFF, but the first 8"
                    f" were: {[word for _, word in words]}"
                )
        else:
            print(f"Skipping full chip erase.")

        print(f"Unlocking Flash for writing...")
        bdm.send_flash_unlock_bypass()
        try:
            with tqdm(total=len(data), unit_scale=True, unit="b") as pbar:
                for i in range(0, len(data), 2):
                    v = (data[i] << 8) | data[i + 1]
                    bdm.send_unlock_bypassed_flash_write(i, v)
                    pbar.update(2)
        finally:
            print(f"Locking Flash to prevent unexpected writes...")
            bdm.exit_flash_unlock_bypass()
        end = time.time()
        print(f"Load complete! Loaded {len(data):,} bytes in {end-start:.2f} seconds.")

    subparser.set_defaults(func=load)


def register_sram_test_command(subparsers):
    subparser = subparsers.add_parser(
        "sram_test",
        help=(
            "Test SRAM attached to the Coldfire. Expects exactly 1MB of RAM, attached via"
            " chip-select port 1, mapped at 0x00200000."
        ),
    )
    subparser.add_argument(
        "--base-address",
        type=lambda s: int(s, 0),
        help="The base address at which the SRAM is attached and mapped.",
        default=0x00200000,
    )
    subparser.add_argument(
        "--max-bytes",
        type=lambda s: int(s, 0),
        default=0x100000,
        help="The maximum number of bytes to test.",
    )

    def test(args, bdm):
        base = args.base_address
        end = base + args.max_bytes

        # First 8 bits of MBAR is ignored; used for mask status bits.
        mbar_value = 0x10000000
        bdm.write_control_register(ControlRegisters.MBAR, mbar_value + 1)

        if args.base_address != 0x00200000:
            raise NotImplementedError(
                "This script only knows how to access a single SRAM chip on chip select 1, mapped"
                " at base address 0x00200000."
            )
        print(f"Mapping SRAM for access at 0x00200000...")
        # TODO: Make these constants, so that we can be more flexible
        # and map any chip-select-attached RAM to any address for testing.
        # All values from https://www.nxp.com/docs/en/data-sheet/MCF5307BUM.pdf
        bdm.write_word(mbar_value + 0x8C, 0x20)  # Base address
        bdm.write_word(mbar_value + 0x96, 0x120)  # Chip select configuration
        bdm.write_longword(mbar_value + 0x90, 0xF0001)  # Size of mapping, plus `1` to indicate OK

        print(f"Writing 0xFFFFFFFF to start of SRAM and polling to ensure value remains constant:")
        bdm.write_longword(base, 0xFFFFFFFF)
        for _ in tqdm(range(200)):
            result = bdm.read_longword(base)
            if result != 0xFFFFFFFF:
                raise ValueError(
                    "Value faded! SRAM does not appear to be holding its value; either SRAM does"
                    " not exist at address 0x{args.base_address:08x}, or the attached SRAM is"
                    " faulty."
                )
        print(f"SRAM appears to retain values properly.")

        print(
            f"Testing RAM from 0x{base:08x} to 0x{end:08x} ({end-base:,} bytes) by writing"
            " low byte of address to each position."
        )

        for address in range(base, end, 4):
            value = address
            bdm.write_longword(address, value)
            saved_value = bdm.read_longword(address)
            if saved_value != value:
                raise ValueError(
                    f"SRAM check failed! Wrote 0x{value:08x} to 0x{address:08x}, but read back"
                    f" 0x{saved_value:08x}! This may indicate that SRAM is faulty."
                )
        print(f"SRAM test passed!")

    subparser.set_defaults(func=test)


def main():
    parser = argparse.ArgumentParser(
        description=(
            "Communicate with an attached Coldfire V3 board (and maybe other versions too) to act"
            " as a simple debugger, via an Arduino serial connection."
        )
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help=(
            "If passed, don't actually connect to a serial port; just queue up commands that would"
            " have otherwise been sent to an attached Arduino."
        ),
    )
    parser.add_argument(
        "--show-commands",
        action="store_true",
        help="If passed, print out a listing of every command sent to the Arduino.",
    )
    parser.add_argument(
        "--serial-port",
        default=None,
        help="The file path of the serial port to connect to.",
    )
    parser.add_argument(
        "--baud-rate",
        type=int,
        default=1000000,
        help=(
            "The baud rate to use when connecting to the Arduino over serial. Must match what the"
            " Arduino expects."
        ),
    )

    subparsers = parser.add_subparsers(title="commands")
    register_dump_command(subparsers)
    register_trace_command(subparsers)
    register_load_command(subparsers)
    register_sram_test_command(subparsers)
    args = parser.parse_args()

    if args.dry_run:
        print("In --dry-run mode; not connecting to serial port.")
        context = nullcontext()
    else:
        if not args.serial_port:
            parser.print_help()
            raise SystemExit(1)
        print(f"Connecting to serial port at {args.serial_port} at {args.baud_rate:,} baud...")
        context = serial.Serial(args.serial_port, args.baud_rate)

    with context as ser:
        if args.dry_run:
            interface = MockColdfireSerialInterface()
        else:
            interface = ColdfireSerialInterface(ser)
        bdm = BDMCommandInterface(interface)

        print(f"Entering debug mode...")
        interface.enter_debug_mode(True)

        if not args.dry_run:
            print(f"Performing consistency check on attached Coldfire processor...")
            bdm.consistency_check()

        if not hasattr(args, "func"):
            print("No command provided; doing nothing. (Pass -h to see available commands.)")
        else:
            args.func(args, bdm)

    if args.dry_run and args.show_commands:
        print(f"Commands sent to Arduino:")
        for command in interface.commands_sent:
            print(f"\t{repr(command)}")


if __name__ == "__main__":
    main()
