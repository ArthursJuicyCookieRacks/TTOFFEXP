"""
Helpers for moving packed DC field values around without unpacking them into
Python objects. The local server stores every field as the raw bytes it was
packed with, exactly like Astron does.
"""

from panda3d.direct import DCPacker


def fieldValueLength(field, data, offset=0):
    """
    Returns the number of bytes the packed value of `field` occupies in
    `data`, starting at `offset`. Raises ValueError if the data is malformed.
    """
    packer = DCPacker()
    packer.setUnpackData(data[offset:])
    packer.beginUnpack(field)
    packer.unpackSkip()
    length = packer.getNumUnpackedBytes()
    if not packer.endUnpack():
        raise ValueError('Malformed value for field %s' % field.getName())
    return length


def readFieldValue(field, di):
    """
    Reads one packed value for `field` out of the DatagramIterator `di` and
    returns it as bytes, leaving `di` positioned after it.
    """
    data = di.getRemainingBytes()
    length = fieldValueLength(field, data)
    di.skipBytes(length)
    return data[:length]


def requiredFields(dclass):
    """
    Returns the required, non-molecular fields of `dclass` in the order
    Astron and Panda3D expect them to appear in a generate.
    """
    fields = []
    for i in range(dclass.getNumInheritedFields()):
        field = dclass.getInheritedField(i)
        if field.isRequired() and not field.asMolecularField():
            fields.append(field)
    return fields


def readRequired(dclass, di):
    """
    Reads the required field block of a generate. Returns {fieldNumber: bytes}.
    """
    values = {}
    for field in requiredFields(dclass):
        values[field.getNumber()] = readFieldValue(field, di)
    return values


def readFieldList(dclass, di, count=None):
    """
    Reads a (uint16 count) list of (uint16 fieldId, value) pairs. If `count` is
    given it is used instead of reading it from `di`. Returns a list of
    (field, bytes) tuples. Unknown fields raise ValueError.
    """
    if count is None:
        count = di.getUint16()
    result = []
    for _ in range(count):
        fieldId = di.getUint16()
        field = dclass.getFieldByIndex(fieldId)
        if field is None:
            raise ValueError('Unknown field %d for class %s' % (fieldId, dclass.getName()))
        result.append((field, readFieldValue(field, di)))
    return result


def splitMolecular(field, data):
    """
    Splits the packed value of a molecular field into [(atomicField, bytes)].
    Atomic fields are returned as they are.
    """
    molecular = field.asMolecularField()
    if not molecular:
        return [(field, data)]
    result = []
    offset = 0
    for i in range(molecular.getNumAtomics()):
        atomic = molecular.getAtomic(i)
        length = fieldValueLength(atomic, data, offset)
        result.append((atomic, data[offset:offset + length]))
        offset += length
    return result


def defaultValue(field):
    return bytes(field.getDefaultValue())


def isVisibleToClient(field, owner=False):
    """
    Mirrors Astron's client_only filter: the fields a client is allowed to see
    in a generate.
    """
    if field.isBroadcast() or field.isClrecv():
        return True
    return owner and field.isOwnrecv()


def formatValue(field, data):
    """
    Formats a packed value in the same text form Astron's YAML database uses.
    """
    packer = DCPacker()
    packer.setUnpackData(data)
    packer.beginUnpack(field)
    text = packer.unpackAndFormat(False)
    if not packer.endUnpack():
        raise ValueError('Malformed value for field %s' % field.getName())
    return text


def parseValue(field, text):
    """
    Parses a value written by formatValue (or by Astron's YAML database) back
    into packed bytes. Raises ValueError on failure.
    """
    packer = DCPacker()
    packer.beginPack(field)
    if not packer.parseAndPack(text) or not packer.endPack():
        raise ValueError('Could not parse %r for field %s' % (text, field.getName()))
    return bytes(packer.getBytes())
