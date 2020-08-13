from ungameboy import Disassembler


if __name__ == '__main__':
    import sys

    path = sys.argv[1]
    dis = Disassembler(path)
    for addr, instr in dis:
        binary = dis.rom[addr:addr+instr.length]
        print(f'{addr:06x} {binary.hex():<6}', instr)
