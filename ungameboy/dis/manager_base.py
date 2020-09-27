from abc import ABCMeta, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .disassembler import Disassembler
    from ..commands import UgbCommandGroup


class AsmManager(metaclass=ABCMeta):
    def __init__(self, disassembler: 'Disassembler'):
        self.asm = disassembler

    @abstractmethod
    def reset(self) -> None:
        pass

    @abstractmethod
    def build_cli_v2(self) -> 'UgbCommandGroup':
        pass

    @abstractmethod
    def save_items(self):
        pass
