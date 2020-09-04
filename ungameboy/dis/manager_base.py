from abc import ABCMeta, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import click
    from .disassembler import Disassembler


class AsmManager(metaclass=ABCMeta):
    def __init__(self, disassembler: 'Disassembler'):
        self.asm = disassembler

    @abstractmethod
    def reset(self) -> None:
        pass

    @abstractmethod
    def build_cli(self) -> 'click.Command':
        pass

    @abstractmethod
    def save_items(self):
        pass
