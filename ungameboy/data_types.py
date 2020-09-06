from dataclasses import dataclass
from typing import Any

__all__ = [
    'Ref', 'IORef', 'ParameterMeta',
    'Byte', 'CgbColor', 'Word', 'SignedByte', 'SPOffset',
]


@dataclass(frozen=True)
class Ref:
    target: Any

    def __repr__(self):
        return f"[{self.target}]"

    @classmethod
    def cast(cls, value):
        return cls(value)


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


class CgbColor(Word):
    symbol = 'color'

    @property
    def rgb_5(self):
        rem, red = divmod(self, 32)
        blue, green = divmod(rem, 32)
        blue %= 32
        return (red, green, blue)

    def __repr__(self):
        r, g, b = self.rgb_5
        return f'#{r:02x}{g:02x}{b:02x}'
