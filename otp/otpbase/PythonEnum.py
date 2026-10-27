from enum import IntEnum as _IntEnum


class IntEnum(_IntEnum):
    # The Python 3 port turned PythonUtil.Enum lists into IntEnums; this keeps
    # the old Enum helpers that the game still calls on them.

    @classmethod
    def getString(cls, value):
        return cls(value).name

    @classmethod
    def hasString(cls, string):
        return string in cls.__members__

    @classmethod
    def fromString(cls, string):
        return cls[string]
