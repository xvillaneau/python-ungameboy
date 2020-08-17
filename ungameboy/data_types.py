from dataclasses import dataclass
from typing import Any

__all__ = [
    'Ref', 'IORef',
    'Byte', 'Word', 'SignedByte', 'SPOffset', 'ParameterMeta',
]


@dataclass(frozen=True)
class Ref:
    target: Any

    def __repr__(self):
        return f"[{self.target}]"


@dataclass(frozen=True)
class IORef(Ref):
    def __repr__(self):
        if isinstance(self.target, Byte):
            return f"[{Word(self.target + 0xff00)}]"
        else:
            return f"[$ff00+{self.target}]"


class ParameterMeta(type):
    symbol = ''
    n_bytes = 1

    def __repr__(cls):
        return cls.symbol


class Byte(int, metaclass=ParameterMeta):
    symbol = 'n8'

    def __bytes__(self):
        return bytes([self])

    def __repr__(self):
        return f"${self:02x}"


class SignedByte(Byte):
    symbol = 'e8'

    def __repr__(self):
        if self < 0x80:
            return f"+${self:02x}"
        else:
            return f"-${256-self:02x}"


class SPOffset(SignedByte):
    symbol = 'SP+e8'

    def __repr__(self):
        return f'SP{super().__repr__()}'


class Word(int, metaclass=ParameterMeta):
    symbol = 'n16'
    n_bytes = 2

    def __bytes__(self):
        return self.to_bytes(2, 'little')

    def __repr__(self):
        return f"${self:04x}"
