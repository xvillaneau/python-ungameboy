from enum import Enum

__all__ = [
    'A', 'B', 'C', 'D', 'E', 'H', 'L',
    'AF', 'BC', 'DE', 'HL', 'SP',
    'Z', 'NZ', 'CY', 'NC',
    'Register', 'DoubleRegister', 'Condition',
    'Operation',
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


class DoubleRegister(str, Enum):
    AF = "AF"
    BC = "BC"
    DE = "DE"
    HL = "HL"
    SP = "SP"

    def __str__(self):
        return self.value


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
    LoadDec = "LDD"
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
