from dataclasses import dataclass
from typing import List, Optional, Tuple

from .models import (
    Op, Operation, Ref, IORef,
    ParameterMeta, Byte, Word, SignedByte, SPOffset,
    A, B, C, D, E, H, L, HL, BC, DE, SP, AF, Z, NZ, CY, NC,
)

__all__ = ['CODE_POINTS', 'CodePoint', 'Instruction']


@dataclass(frozen=True)
class Instruction:
    type: Operation
    length: int
    args: Tuple

    def __str__(self):
        args_str = ', '.join(map(str, self.args))
        return f"{self.type} {args_str}".strip().lower()


class CodePoint:
    param_type: Optional[ParameterMeta]

    def __init__(self, code_point, op_type: Operation, *args):
        self.code_point: int = code_point
        self.type = op_type
        self.visual_args = args

        self.length = 1
        self.param_type = None
        for arg in args:
            if isinstance(arg, Ref):
                arg = arg.target
            if isinstance(arg, ParameterMeta):
                self.param_type = arg
                self.length = arg.n_bytes + 1
                break

    def __repr__(self):
        args_str = ', '.join(map(str, self.visual_args))
        return f"{self.type} {args_str}".strip().lower()

    def make_instance(self, param=b'') -> Instruction:
        if param is None and self.length > 1:
            raise ValueError(f"Expected {self.length - 1} arguments, got none")
        if self.param_type is not None:
            param = self.param_type(int.from_bytes(param, 'little'))

        args = []
        for arg in self.visual_args:
            if isinstance(arg, ParameterMeta):
                args.append(param)
            elif isinstance(arg, Ref) and isinstance(arg.target, ParameterMeta):
                # noinspection PyArgumentList
                args.append(arg.__class__(param))
            else:
                args.append(arg)

        return Instruction(
            self.type,
            self.length,
            tuple(args),
        )


class BitwiseOps(CodePoint):

    def __init__(self, code_point):
        super().__init__(code_point, Op.Invalid)
        self.length = 2
        self.param_type = Byte

    def make_instance(self, param=b'') -> Instruction:
        param = self.param_type(int.from_bytes(param, 'little'))
        op_type, bit, operand = BITWISE_CODE_POINTS[param]
        args = (operand,) if bit is None else (bit, operand)

        return Instruction(
            type=op_type,
            length=2,
            args=args,
        )


def _make_bitwise_code_points():
    operands = [B, C, D, E, H, L, Ref(HL), A]
    simple_ops = [
        Op.RotLeft, Op.RotRight,
        Op.RotLeftCarry, Op.RotRightCarry,
        Op.ShiftLeftZero, Op.ShiftRightCopy,
        Op.SwapNibbles, Op.ShiftRightZero,
    ]
    bit_ops = [Op.Invalid, Op.GetBit, Op.ResetBit, Op.SetBit]

    code_points = []
    for code in range(256):
        op, reg = divmod(code, 8)
        if op < 8:
            data = (simple_ops[op], None, operands[reg])
        else:
            op, bit = divmod(op, 8)
            data = (bit_ops[op], bit, operands[reg])
        code_points.append(data)
    return code_points


BITWISE_CODE_POINTS = _make_bitwise_code_points()


META_INSTRUCTIONS = [
    # 0x00
    Op.NoOp,
    (Op.Load, BC, Word),
    (Op.Load, Ref(BC), A),
    (Op.Increment, BC),
    (Op.Increment, B),
    (Op.Decrement, B),
    (Op.Load, B, Byte),
    Op.ARotLeft,
    # 0x08
    (Op.Load, Ref(Word), SP),
    (Op.Add, HL, BC),
    (Op.Load, A, Ref(BC)),
    (Op.Decrement, BC),
    (Op.Increment, C),
    (Op.Decrement, C),
    (Op.Load, C, Byte),
    Op.ARotRight,

    # 0x10
    Op.Stop,
    (Op.Load, DE, Word),
    (Op.Load, Ref(DE), A),
    (Op.Increment, DE),
    (Op.Increment, D),
    (Op.Decrement, D),
    (Op.Load, D, Byte),
    Op.ARotLeftCarry,
    # 0x18
    (Op.RelJump, SignedByte),
    (Op.Add, HL, DE),
    (Op.Load, A, Ref(DE)),
    (Op.Decrement, DE),
    (Op.Increment, E),
    (Op.Decrement, E),
    (Op.Load, E, Byte),
    Op.ARotRightCarry,

    # 0x20
    (Op.RelJump, NZ, SignedByte),
    (Op.Load, HL, Word),
    (Op.LoadInc, Ref(HL), A),
    (Op.Increment, HL),
    (Op.Increment, H),
    (Op.Decrement, H),
    (Op.Load, H, Byte),
    Op.DecimalAdjust,
    # 0x28
    (Op.RelJump, Z, SignedByte),
    (Op.Add, HL, HL),
    (Op.LoadInc, A, Ref(HL)),
    (Op.Decrement, HL),
    (Op.Increment, L),
    (Op.Decrement, L),
    (Op.Load, L, Byte),
    Op.Complement,

    # 0x30
    (Op.RelJump, NC, SignedByte),
    (Op.Load, SP, Word),
    (Op.LoadDec, Ref(HL), A),
    (Op.Increment, SP),
    (Op.Increment, Ref(HL)),
    (Op.Decrement, Ref(HL)),
    (Op.Load, Ref(HL), Byte),
    Op.SetCarry,
    # 0x38
    (Op.RelJump, CY, SignedByte),
    (Op.Add, HL, SP),
    (Op.LoadDec, A, Ref(HL)),
    (Op.Decrement, SP),
    (Op.Increment, A),
    (Op.Decrement, A),
    (Op.Load, L, Byte),
    Op.InvCarry,

    # 0x40
    (Op.Load, B, B),
    (Op.Load, B, C),
    (Op.Load, B, D),
    (Op.Load, B, E),
    (Op.Load, B, H),
    (Op.Load, B, L),
    (Op.Load, B, Ref(HL)),
    (Op.Load, B, A),
    # 0x48
    (Op.Load, C, B),
    (Op.Load, C, C),
    (Op.Load, C, D),
    (Op.Load, C, E),
    (Op.Load, C, H),
    (Op.Load, C, L),
    (Op.Load, C, Ref(HL)),
    (Op.Load, C, A),

    # 0x50
    (Op.Load, D, B),
    (Op.Load, D, C),
    (Op.Load, D, D),
    (Op.Load, D, E),
    (Op.Load, D, H),
    (Op.Load, D, L),
    (Op.Load, D, Ref(HL)),
    (Op.Load, D, A),
    # 0x58
    (Op.Load, E, B),
    (Op.Load, E, C),
    (Op.Load, E, D),
    (Op.Load, E, E),
    (Op.Load, E, H),
    (Op.Load, E, L),
    (Op.Load, E, Ref(HL)),
    (Op.Load, E, A),

    # 0x60
    (Op.Load, H, B),
    (Op.Load, H, C),
    (Op.Load, H, D),
    (Op.Load, H, E),
    (Op.Load, H, H),
    (Op.Load, H, L),
    (Op.Load, H, Ref(HL)),
    (Op.Load, H, A),
    # 0x68
    (Op.Load, L, B),
    (Op.Load, L, C),
    (Op.Load, L, D),
    (Op.Load, L, E),
    (Op.Load, L, H),
    (Op.Load, L, L),
    (Op.Load, L, Ref(HL)),
    (Op.Load, L, A),

    # 0x70
    (Op.Load, Ref(HL), B),
    (Op.Load, Ref(HL), C),
    (Op.Load, Ref(HL), D),
    (Op.Load, Ref(HL), E),
    (Op.Load, Ref(HL), H),
    (Op.Load, Ref(HL), L),
    Op.Halt,
    (Op.Load, Ref(HL), A),
    # 0x78
    (Op.Load, A, B),
    (Op.Load, A, C),
    (Op.Load, A, D),
    (Op.Load, A, E),
    (Op.Load, A, H),
    (Op.Load, A, L),
    (Op.Load, A, Ref(HL)),
    (Op.Load, A, A),

    # 0x80
    (Op.Add, A, B),
    (Op.Add, A, C),
    (Op.Add, A, D),
    (Op.Add, A, E),
    (Op.Add, A, H),
    (Op.Add, A, L),
    (Op.Add, A, Ref(HL)),
    (Op.Add, A, A),
    # 0x88
    (Op.AddWCarry, A, B),
    (Op.AddWCarry, A, C),
    (Op.AddWCarry, A, D),
    (Op.AddWCarry, A, E),
    (Op.AddWCarry, A, H),
    (Op.AddWCarry, A, L),
    (Op.AddWCarry, A, Ref(HL)),
    (Op.AddWCarry, A, A),

    # 0x90
    (Op.Subtract, A, B),
    (Op.Subtract, A, C),
    (Op.Subtract, A, D),
    (Op.Subtract, A, E),
    (Op.Subtract, A, H),
    (Op.Subtract, A, L),
    (Op.Subtract, A, Ref(HL)),
    (Op.Subtract, A, A),
    # 0x98
    (Op.SubtractWCarry, A, B),
    (Op.SubtractWCarry, A, C),
    (Op.SubtractWCarry, A, D),
    (Op.SubtractWCarry, A, E),
    (Op.SubtractWCarry, A, H),
    (Op.SubtractWCarry, A, L),
    (Op.SubtractWCarry, A, Ref(HL)),
    (Op.SubtractWCarry, A, A),

    # 0xA0
    (Op.And, A, B),
    (Op.And, A, C),
    (Op.And, A, D),
    (Op.And, A, E),
    (Op.And, A, H),
    (Op.And, A, L),
    (Op.And, A, Ref(HL)),
    (Op.And, A, A),
    # 0xA8
    (Op.Xor, A, B),
    (Op.Xor, A, C),
    (Op.Xor, A, D),
    (Op.Xor, A, E),
    (Op.Xor, A, H),
    (Op.Xor, A, L),
    (Op.Xor, A, Ref(HL)),
    (Op.Xor, A, A),

    # 0xB0
    (Op.Or, A, B),
    (Op.Or, A, C),
    (Op.Or, A, D),
    (Op.Or, A, E),
    (Op.Or, A, H),
    (Op.Or, A, L),
    (Op.Or, A, Ref(HL)),
    (Op.Or, A, A),
    # 0xB8
    (Op.Compare, A, B),
    (Op.Compare, A, C),
    (Op.Compare, A, D),
    (Op.Compare, A, E),
    (Op.Compare, A, H),
    (Op.Compare, A, L),
    (Op.Compare, A, Ref(HL)),
    (Op.Compare, A, A),

    # 0xC0
    (Op.Return, NZ),
    (Op.Pop, BC),
    (Op.AbsJump, NZ, Word),
    (Op.AbsJump, Word),
    (Op.Call, NZ, Word),
    (Op.Push, BC),
    (Op.Add, A, Byte),
    (Op.Vector, 0x00),
    # 0xC8
    (Op.Return, Z),
    Op.Return,
    (Op.AbsJump, Z, Word),
    BitwiseOps,
    (Op.Call, Z, Word),
    (Op.Call, Word),
    (Op.AddWCarry, A, Byte),
    (Op.Vector, 0x08),

    # 0xD0
    (Op.Return, NC),
    (Op.Pop, DE),
    (Op.AbsJump, NC, Word),
    None,
    (Op.Call, NC, Word),
    (Op.Push, DE),
    (Op.Subtract, A, Byte),
    (Op.Vector, 0x10),
    # 0xD8
    (Op.Return, CY),
    Op.ReturnIntEnable,
    (Op.AbsJump, CY, Word),
    None,
    (Op.Call, CY, Word),
    None,
    (Op.SubtractWCarry, A, Byte),
    (Op.Vector, 0x18),

    # 0xE0
    (Op.LoadFast, IORef(Byte), A),
    (Op.Pop, HL),
    (Op.LoadFast, IORef(C), A),
    None,
    None,
    (Op.Push, HL),
    (Op.And, A, Byte),
    (Op.Vector, 0x20),
    # 0xE8
    (Op.Add, SP, Byte),
    (Op.AbsJump, HL),
    (Op.Load, Ref(Word), A),
    None,
    None,
    None,
    (Op.Xor, A, Byte),
    (Op.Vector, 0x28),

    # 0xF0
    (Op.LoadFast, A, IORef(Byte)),
    (Op.Pop, AF),
    (Op.LoadFast, A, IORef(C)),
    Op.IntDisable,
    None,
    (Op.Push, AF),
    (Op.Or, A, Byte),
    (Op.Vector, 0x30),
    # 0xF8
    (Op.Load, HL, SPOffset),
    (Op.Load, SP, HL),
    (Op.Load, A, Ref(Word)),
    Op.IntEnable,
    None,
    None,
    (Op.Compare, A, Byte),
    (Op.Vector, 0x38),
]


def _make_code_points():
    code_points = []
    for _pos, _data in enumerate(META_INSTRUCTIONS):
        if _data is BitwiseOps:
            code_points.append(_data(_pos))
            continue

        _args = ()
        _type = Op.Invalid
        if isinstance(_data, Operation):
            _type = _data
        elif isinstance(_data, tuple):
            _type, *_args = _data

        code_points.append(CodePoint(_pos, _type, *_args))
    return code_points


CODE_POINTS: List[CodePoint] = _make_code_points()
