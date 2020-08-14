from ungameboy import ROMBytes


if __name__ == '__main__':
    import sys

    path = sys.argv[1]
    rom = ROMBytes(path)
    for instr in rom.decode():
        print(f'{instr.address:06x} {instr.bytes.hex():<6} {instr}')
