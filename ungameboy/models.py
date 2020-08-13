from dataclasses import dataclass
from enum import Enum
from typing import Any

__all__ = [
    'A', 'B', 'C', 'D', 'E', 'H', 'L',
    'AF', 'BC', 'DE', 'HL', 'SP',
    'Z', 'NZ', 'CY', 'NC',
    'Register', 'DoubleRegister', 'Condition',
    'Ref', 'IORef', 'Op', 'Operation',
    'Byte', 'Word', 'SignedByte', 'SPOffset', 'ParameterMeta',
]


class Register(str, Enum):
    A = "A"
    B = "B"
    C = "C"
    D = "D"
    E = "E"
    H = "H"
    L = "L"

    def __str__(self):
        return self.value

    def __repr__(self):
        return f"<Register {self.value}>"


class DoubleRegister(str, Enum):
    AF = "AF"
    BC = "BC"
    DE = "DE"
    HL = "HL"
    SP = "SP"

    def __str__(self):
        return self.value

    def __repr__(self):
        return f"<Register {self.value}>"


# Unpack the enums into more convenient variables
A, B, C, D, E, H, L = Register
AF, BC, DE, HL, SP = DoubleRegister


class Condition(str, Enum):
    zero_set = "Z"
    zero_reset = "NZ"
    carry_set = "C"
    carry_reset = "NC"

    def __str__(self):
        return self.value

    def __repr__(self):
        return f"<Cond {self.value}>"


Z, NZ, CY, NC = Condition


class Operation(str, Enum):
    Invalid = "INVALID"

    # CPU commands
    NoOp = "NOP"
    Stop = "STOP"
    Halt = "HALT"
    IntEnable = "EI"
    IntDisable = "DI"
    InvCarry = "CCF"
    SetCarry = "SCF"

    # Jump/call commands
    AbsJump = "JP"
    RelJump = "JR"
    Call = "CALL"
    Return = "RET"
    ReturnIntEnable = "RETI"
    Vector = "RST"

    # Loading data
    Load = "LD"
    LoadFast = "LDH"
    LoadInc = "LDI"
    LoadDec = "LDH"
    Push = "PUSH"
    Pop = "POP"

    # Arithmetics
    Add = "ADD"
    AddWCarry = "ADC"
    Subtract = "SUB"
    SubtractWCarry = "SBC"
    And = "AND"
    Xor = "XOR"
    Or = "OR"
    Compare = "CP"
    Increment = "INC"
    Decrement = "DEC"
    DecimalAdjust = "DAA"
    Complement = "CPL"

    # Bitwise operations
    GetBit = "BIT"
    SetBit = "SET"
    ResetBit = "RES"
    ARotLeft = "RLCA"
    ARotLeftCarry = "RLA"
    ARotRight = "RRCA"
    ARotRightCarry = "RRA"
    RotLeft = "RLC"
    RotLeftCarry = "RL"
    RotRight = "RRC"
    RotRightCarry = "RR"
    ShiftLeftZero = "SLA"
    ShiftRightZero = "SRL"
    ShiftRightCopy = "SRA"
    SwapNibbles = "SWAP"

    def __str__(self):
        return self.value


Op = Operation


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
