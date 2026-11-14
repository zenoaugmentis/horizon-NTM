"""Inspection codec extracted from the supplied manual S03 scripts.

No file I/O on import. Not a production NBT implementation; see README.
"""

import struct

raw = b""

pos = 0

TYPES = [
    "End", "Byte", "Short", "Int", "Long", "Float", "Double",
    "ByteArray", "String", "List", "Compound", "IntArray",
]

def take(n):
    global pos
    if n < 0 or pos + n > len(raw):
        raise ValueError(f"Invalid read: offset={pos}, size={n}")
    value = raw[pos:pos + n]
    pos += n
    return value

def number(fmt):
    return struct.unpack(">" + fmt, take(struct.calcsize(">" + fmt)))[0]

def string():
    # Inspection only: retain Java surrogate units; accept modified UTF-8 NUL.
    data = take(number("H")).replace(b"\xc0\x80", b"\x00")
    return data.decode("utf-8", errors="surrogatepass")

def count():
    n = number("i")
    if n < 0:
        raise ValueError("Negative array/list length")
    return n

def payload(kind, depth=0):
    if depth > 100:
        raise ValueError("Excessive nesting")
    if 1 <= kind <= 6:
        return number({1: "b", 2: "h", 3: "i",
                       4: "q", 5: "f", 6: "d"}[kind])
    if kind == 7:
        return take(count())
    if kind == 8:
        return string()
    if kind == 9:
        element_type = number("B")
        n = count()
        if not 0 <= element_type <= 11 or (element_type == 0 and n):
            raise ValueError("Invalid list element type")
        return element_type, [payload(element_type, depth + 1) for _ in range(n)]
    if kind == 10:
        result = {}
        while True:
            child_type = number("B")
            if child_type == 0:
                return result
            name = string()
            if name in result:
                raise ValueError(f"Duplicate tag: {name}")
            result[name] = (child_type, payload(child_type, depth + 1))
    if kind == 11:
        return [number("i") for _ in range(count())]
    raise ValueError(f"Unsupported tag type: {kind}")

def describe(kind, value):
    if kind == 9:
        element_type, items = value
        return f"List<{TYPES[element_type]}>[{len(items)}]"
    if kind in (7, 10, 11):
        return f"{TYPES[kind]}[{len(value)}]"
    return f"{TYPES[kind]} = {value!r}"

def nibble(data, index):
    return (data[index // 2] >> (4 * (index % 2))) & 15

def pack_number(fmt, value):
    return struct.pack(">" + fmt, value)

def encode_string(value):
    # Java modified UTF-8: кодирование по 16-битным единицам UTF-16.
    units = value.encode("utf-16-be", errors="surrogatepass")
    result = bytearray()
    for i in range(0, len(units), 2):
        c = (units[i] << 8) | units[i + 1]
        if 1 <= c <= 127:
            result.append(c)
        elif c <= 0x7FF:
            result.extend((0xC0 | (c >> 6), 0x80 | (c & 63)))
        else:
            result.extend((
                0xE0 | (c >> 12),
                0x80 | ((c >> 6) & 63),
                0x80 | (c & 63),
            ))
    return pack_number("H", len(result)) + result

def encode_payload(kind, value):
    if 1 <= kind <= 6:
        return pack_number(
            {1: "b", 2: "h", 3: "i", 4: "q", 5: "f", 6: "d"}[kind],
            value,
        )
    if kind == 7:
        return pack_number("i", len(value)) + value
    if kind == 8:
        return encode_string(value)
    if kind == 9:
        element_type, items = value
        return (
            pack_number("B", element_type)
            + pack_number("i", len(items))
            + b"".join(encode_payload(element_type, item) for item in items)
        )
    if kind == 10:
        return b"".join(
            pack_number("B", child_type)
            + encode_string(name)
            + encode_payload(child_type, child_value)
            for name, (child_type, child_value) in value.items()
        ) + b"\x00"
    if kind == 11:
        return pack_number("i", len(value)) + b"".join(
            pack_number("i", item) for item in value
        )
    raise ValueError(f"Unsupported tag type: {kind}")

def decode(data):
    global raw, pos
    raw, pos = data, 0
    kind = number("B")
    name = string()
    if kind != 10:
        raise ValueError("Root must be Compound")
    value = payload(kind)
    if pos != len(raw):
        raise ValueError("Trailing NBT bytes")
    return name, value


def encode(name, value):
    return b"\x0a" + encode_string(name) + encode_payload(10, value)
