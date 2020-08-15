from ungameboy import ROMBytes


if __name__ == '__main__':
    import sys

    rom = ROMBytes.from_path(sys.argv[1])
    for instr in rom.decode():
        print(f'{instr.address} {instr.bytes.hex():<6} {instr}')
