from .manager_base import AsmManager
from ..address import ROM, Address


class AnalysisManager(AsmManager):
    def detect_empty_banks(self):
        for bank in range(1, self.asm.rom.n_banks):
            if any(self.asm.rom.rom[bank * 0x4000:(bank + 1) * 0x4000]):
                continue
            bank_start = Address(ROM, bank, 0)
            if self.asm.data.get_data(bank_start) is None:
                self.asm.data.create_empty(bank_start, 0x4000)

    def build_cli_v2(self):
        from ..commands import UgbCommandGroup

        cli = UgbCommandGroup(self.asm, "analyze")
        cli.add_command("detect_empty_banks", self.detect_empty_banks)
        return cli

    def reset(self):
        return

    def save_items(self):
        return ()
