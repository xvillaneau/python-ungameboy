from typing import Dict, Iterator, List, NamedTuple, Optional, Tuple

from .address import Address
from .data_structures import SortedMapping


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


class LabelManager:
    def __init__(self):
        self._globals: SortedMapping[Address, List[str]] = SortedMapping()
        self._locals: SortedMapping[Address, List[str]] = SortedMapping()

        self._all: SortedMapping[Address, List[Label]] = SortedMapping()

        self._by_address: Dict[Address, List[str]] = {}
        self._by_name: SortedMapping[str, Address] = SortedMapping()

    def _rebuild_all(self):
        self._all.clear()

        for addr, names in self._globals.items():
            for name in names:
                self._all.setdefault(addr, []).append(Label(addr, name))

        for addr, names in self._locals.items():
            try:
                _, scope = self._globals.get_le(addr)
                scope = scope[-1]
            except LookupError:
                continue

            for name in names:
                self._all.setdefault(addr, []).append(Label(addr, scope, name))

    def get_labels(self, address: Address) -> List[Label]:
        return self._all.get(address, [])

    def list_items(self) -> Iterator[Label]:
        for labels in self._all.values():
            yield from labels

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

    def scope_at(self, address: Address) -> Optional[Tuple[Address, str]]:
        try:
            addr, names = self._globals.get_le(address)
        except LookupError:
            return None
        return addr, names[-1]

    def _add_local(self, address: Address, name: str):
        _glob, _, _loc = name.partition('.')
        if '.' in _loc:
            raise ValueError(f"Invalid label name: {name}")

        try:
            scope_start, scope_names = self._globals.get_le(address)
        except LookupError:
            raise ValueError("Local labels must be in scope of a global label")
        if _glob != '' and _glob not in scope_names:
            raise ValueError(f"Global label {_glob} not in scope at {address}")

        scope_name = scope_names[-1]
        current_locals = self.locals_at(scope_start)
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
        self._by_name[name] = address
        self._rebuild_all()

    def create(self, address: Address, name: str):
        if "." in name:
            self._add_local(address, name)
        else:
            self._add_global(address, name)
