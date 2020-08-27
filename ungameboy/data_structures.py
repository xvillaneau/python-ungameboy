from bisect import bisect_left, bisect_right
from operator import itemgetter
from typing import Iterator, List, Sequence, MutableMapping, Tuple, TypeVar

__all__ = ['SortedMapping', 'SortedStrMapping', 'StateStack']

K = TypeVar('K')
V = TypeVar('V')
T = TypeVar('T')


class SortedMapping(MutableMapping[K, V]):
    def __init__(self, items: List[Tuple[K, V]] = ()):
        self._keys: List[K] = []
        self._values: List[V] = []

        pre_sorted = sorted(items, key=itemgetter(0))

        for key, value in pre_sorted:
            if self._keys and self._keys[-1] == key:
                self._values[-1] = value
            else:
                self._keys.append(key)
                self._values.append(value)

    def __len__(self):
        return len(self._keys)

    def __iter__(self):
        return iter(self._keys)

    def __getitem__(self, item: K) -> V:
        pos = bisect_left(self._keys, item)
        if pos >= len(self) or self._keys[pos] != item:
            raise KeyError(item)
        return self._values[pos]

    def __setitem__(self, key: K, value: V):
        pos = bisect_left(self._keys, key)
        if pos < len(self) and self._keys[pos] == key:
            self._values[pos] = value
        else:
            self._keys.insert(pos, key)
            self._values.insert(pos, value)

    def __delitem__(self, key: K):
        pos = bisect_left(self._keys, key)
        if self._keys[pos] != key:
            raise KeyError(key)
        self._keys.pop(pos)
        self._values.pop(pos)

    def clear(self) -> None:
        self._keys.clear()
        self._values.clear()

    def _item(self, pos: int) -> Tuple[K, V]:
        return self._keys[pos], self._values[pos]

    def iter_from(self, start: K) -> Iterator[Tuple[K, V]]:
        pos = bisect_left(self._keys, start)
        while pos < len(self):
            yield self._item(pos)
            pos += 1

    def get_le(self, item: K) -> Tuple[K, V]:
        pos = bisect_right(self._keys, item)
        if pos == 0:
            raise KeyError(item)
        return self._item(pos - 1)

    def get_ge(self, item: K) -> Tuple[K, V]:
        pos = bisect_right(self._keys, item)
        if pos > 0 and self._keys[pos - 1] == item:
            pos -= 1
        elif pos >= len(self):
            raise KeyError(item)
        return self._item(pos)

    def get_gt(self, item: K) -> Tuple[K, V]:
        pos = bisect_right(self._keys, item)
        if pos >= len(self):
            raise KeyError(item)
        return self._item(pos)


class SortedStrMapping(SortedMapping[str, V]):
    """Special case for string keys, where searching is implemented"""

    def search(self, string: str) -> Iterator[str]:
        pos = bisect_left(self._keys, string)
        lim = len(self)

        if not pos < lim:
            return
        key = self._keys[pos]

        while key.startswith(string):
            yield key
            pos += 1
            if not pos < lim:
                break
            key = self._keys[pos]


class StateStack(Sequence[T]):
    def __init__(self):
        self._stack: List[T] = []
        self._head = 0

    def push(self, item: T):
        if len(self._stack) > self._head:
            self._stack = self._stack[:self._head]
        self._stack.append(item)
        self._head += 1

    @property
    def head(self):
        return self._stack[self._head - 1]

    @property
    def can_undo(self) -> bool:
        return self._head > 1

    def undo(self) -> T:
        if not self.can_undo:
            raise IndexError("At bottom of stack, cannot undo")
        self._head -= 1
        return self.head

    @property
    def can_redo(self) -> bool:
        return len(self._stack) > self._head

    def redo(self) -> T:
        if not self.can_redo:
            raise IndexError("At top of stack, cannot redo")
        self._head += 1
        return self.head

    def __getitem__(self, i: int) -> T:
        return self._stack[i]

    def __len__(self) -> int:
        return self._head