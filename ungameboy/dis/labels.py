from typing import TYPE_CHECKING, Iterator, List, NamedTuple, Tuple

from .manager_base import AsmManager
from ..address import Address, MemoryType
from ..commands import LabelName, UgbCommandGroup
from ..data_structures import AddressMapping, SortedStrMapping

if TYPE_CHECKING:
    from .disassembler import Disassembler

__all__ = ['Label', 'LabelManager', 'LabelOffset']


class Label(NamedTuple):
    address: Address
    global_name: str
    local_name: str = ""

    @property
    def name(self):
        name = self.global_name
        if self.local_name:
            name += f".{self.local_name}"
        return name

    @property
    def is_global(self) -> bool:
        return not self.local_name


class LabelOffset(NamedTuple):
    label: Label
    offset: int

    @property
    def address(self):
        return self.label.address + self.offset


class LabelManager(AsmManager):
    def __init__(self, asm: 'Disassembler'):
        super().__init__(asm)

        self._globals: AddressMapping[List[str]] = AddressMapping()
        self._locals: AddressMapping[List[str]] = AddressMapping()
        self._all: AddressMapping[List[Label]] = AddressMapping()
        self._by_name: SortedStrMapping[Address] = SortedStrMapping()

    def reset(self) -> None:
        self._globals.clear()
        self._locals.clear()
        self._all.clear()
        self._by_name.clear()

    def __contains__(self, item):
        if isinstance(item, str):
            return item in self._by_name
        return False

    def _rebuild_all(self):
        self._all.clear()
        self._by_name.clear()

        for addr, names in self._globals.items():
            for name in names:
                self._all.setdefault(addr, []).append(Label(addr, name))
                self._by_name[name] = addr

        for addr, names in self._locals.items():
            try:
                _, scope = self._globals.get_le(addr)
                scope = scope[-1]
            except LookupError:
                continue

            for name in names:
                self._all.setdefault(addr, []).append(Label(addr, scope, name))
                self._by_name[f'{scope}.{name}'] = addr

    def lookup(self, name: str) -> Label:
        addr = self._by_name[name]
        glob, _, loc = name.partition(".")
        return Label(addr, glob, loc)

    def search(self, string: str):
        search_local = '.' in string
        for name in self._by_name.search(string):
            if '.' not in name or search_local:
                yield name

    def get_labels(self, address: Address) -> List[Label]:
        return self._all.get(address, [])

    def get_all_in_bank(
            self, mem_type: MemoryType, bank: int
    ) -> Iterator[Tuple[Address, List[Label]]]:
        """Iterate over all labels in a given bank"""
        start = Address(mem_type, bank, 0)
        for addr, labels in self._all.iter_from(start):
            if (addr.bank, addr.type) != (bank, mem_type):
                return
            yield addr, labels

    def locals_at(self, addr: Address) -> List[Tuple[Address, str]]:
        try:
            scope_end, _ = self._globals.get_gt(addr)
        except LookupError:
            scope_end = None

        _locals = []
        for addr, names in self._locals.iter_from(addr):
            if scope_end is not None and addr >= scope_end:
                break
            for name in names:
                _locals.append((addr, name))

        return _locals

    def scope_at(self, address: Address) -> List[Label]:
        try:
            addr, names = self._globals.get_le(address)
        except LookupError:
            return []
        # TODO: Also consider sections as scope boundaries
        if (addr.type, addr.bank) != (address.type, address.bank):
            return []
        return [Label(addr, name) for name in names]

    def _add_local(self, address: Address, name: str):
        _glob, _, _loc = name.partition('.')
        if '.' in _loc:
            raise ValueError(f"Invalid label name: {name}")

        scope = self.scope_at(address)
        if not scope:
            raise ValueError("Local labels must be in scope of a global label")

        if _glob != '' and all(lb.name != _glob for lb in scope):
            raise ValueError(f"Global label {_glob} not in scope at {address}")

        scope_name = scope[-1].global_name
        current_locals = self.locals_at(scope[-1].address)
        if any(n == _loc for _, n in current_locals):
            raise ValueError(f"Label {scope_name}.{_loc} already exists")

        label = Label(address, scope_name, _loc)
        self._locals.setdefault(address, []).append(_loc)
        self._all.setdefault(address, []).append(label)
        self._by_name[label.name] = address

    def _add_global(self, address, name: str):
        if '.' in name:
            raise ValueError("Global labels cannot have a '.' in their name")

        cur_addr = self._by_name.get(name)
        if cur_addr is None:
            pass
        elif cur_addr == address:
            return
        else:
            raise ValueError(f"Label {name} already exists at {cur_addr}")

        self._globals.setdefault(address, []).append(name)
        if not self.locals_at(address):
            label = Label(address, name)
            self._all.setdefault(address, []).append(label)
            self._by_name[name] = address
        else:
            self._rebuild_all()

    def create(self, address: Address, name: LabelName):
        if "." in name:
            self._add_local(address, name)
        else:
            self._add_global(address, name)
        self.asm.xrefs.index_from(address)

    def auto_create(self, address: Address, local=False):
        if address.bank < 0:
            raise ValueError("Cannot place label at unknown bank")
        name = (
            f"{'.' * local}"
            f"auto_{address.type.name}"
            f"_{address.bank:x}"
            f"_{address.memory_address:04x}"
        )
        self.create(address, LabelName(name))

    def rename(self, old_name: LabelName, new_name: LabelName):
        if old_name not in self._by_name:
            raise KeyError(f"Label {old_name} not found")
        if old_name == new_name:
            return
        if new_name in self._by_name:
            raise ValueError(f"Label {new_name} already exists")

        address = self._by_name[old_name]
        if '.' in old_name:
            # Rename local
            old_glob, _, old_loc = old_name.partition('.')
            new_glob, _, new_loc = new_name.partition('.')
            assert old_glob and old_loc and '.' not in old_loc

            if not new_loc or '.' in new_loc:
                raise ValueError("Invalid local label name")
            if new_glob:
                raise ValueError("Local label rename must use .<name>")

            # Using assert because those conditions shouldn't happen
            scope = self.scope_at(address)
            assert any(lb.name == old_glob for lb in scope)

            locals_there = self._locals[address]
            pos = locals_there.index(old_loc)
            locals_there[pos] = new_loc

        else:
            if '.' in new_name:
                raise ValueError("Invalid global label name")
            # Rename global
            globals_there = self._globals[address]
            pos = globals_there.index(old_name)
            globals_there[pos] = new_name

        self._rebuild_all()

    def delete(self, name: LabelName):
        if name not in self._by_name:
            raise KeyError(f"Label {name} not found")

        address = self._by_name[name]
        if '.' in name:
            # Deleting local label
            glob, _, loc = name.partition('.')
            assert glob and loc and '.' not in loc

            locals_here = self._locals[address]
            if len(locals_here) == 1:
                del self._locals[address]
            else:
                locals_here.remove(loc)

        else:
            # Deleting global label
            globals_here = self._globals[address]
            locals_here = self.locals_at(address)

            if locals_here and len(globals_here) == 1:
                # This is a special case where the local labels should
                # be passed under a global at a different position. A
                # lot can go wrong, so we need to check.
                # First, check that a new scope even exists
                if address.offset == 0:
                    raise ValueError("No new global label found for locals")
                scope = self.scope_at(address - 1)
                if not scope:
                    raise ValueError("No new global label found for locals")

                # Then, we need to check that there are no labels with
                # the same name in the scopes that will be merged.
                new_locals = {name for _, name in self.locals_at(scope[0].address)}
                merged_locals = {name for _, name in locals_here}
                conflicts = new_locals & merged_locals
                if conflicts:
                    raise ValueError(
                        "Local labels with same names already exist in the "
                        f"new scope: {', '.join(conflicts)}"
                    )

            if len(globals_here) == 1:
                del self._globals[address]
            else:
                globals_here.remove(name)

        self._rebuild_all()

    def build_cli_v2(self) -> UgbCommandGroup:
        labels_cli = UgbCommandGroup(self.asm, "label")
        labels_cli.add_command("create", self.create)
        labels_cli.add_command("auto", self.auto_create)
        labels_cli.add_command("rename", self.rename)
        labels_cli.add_command("delete", self.delete)
        return labels_cli

    def save_items(self):
        for labels in self._all.values():
            for label in labels:
                yield ('label', 'create', label.address, label.name)
