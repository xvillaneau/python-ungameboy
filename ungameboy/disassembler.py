from .instructions import CODE_POINTS


class Disassembler:

    def __init__(self, rom_path):
        # Just store the entire ROM in memory
        with open(rom_path, 'rb') as rom_file:
            self.rom = rom_file.read()

    def __iter__(self):
        nop_start = None

        i, end = 0, len(self.rom)
        nop = CODE_POINTS[0]

        while i < end:
            code = self.rom[i]

            if not code:  # NOP
                if nop_start is None:
                    nop_start = i
                i += 1
                continue

            if nop_start is not None:
                if i & 0x3FFF != 0:  # Not on ROM bank boundary
                    yield from (
                        (j, nop.make_instance(j))
                        for j in range(nop_start, i)
                    )
                nop_start = None

            instr = CODE_POINTS[code]
            if instr.length >= 2:
                parameter = self.rom[i+1:i+instr.length]
            else:  # length = 1
                parameter = b''

            yield i, instr.make_instance(parameter)
            i += instr.length
