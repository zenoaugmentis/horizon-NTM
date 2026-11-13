"""S04 initial protocol-5 exchanges. Standard library; no import-time network I/O."""
import argparse
import io
import json
import socket
import struct
import uuid

MAX_BODY = 1024 * 1024  # Tool limit, not a measured protocol limit.


def check(condition, message):
    if not condition:
        raise ValueError(message)


def varint(value):
    check(-(1 << 31) <= value < (1 << 31), "VarInt out of int32 range")
    value &= 0xffffffff
    result = bytearray()
    while True:
        part = value & 0x7f
        value >>= 7
        result.append(part | (0x80 if value else 0))
        if not value:
            return bytes(result)


def exact(stream, count):
    check(count >= 0, "Negative read length")
    data = bytearray()
    while len(data) < count:
        part = stream.read(count - len(data))
        if not part:
            raise EOFError("Connection closed or packet truncated")
        data.extend(part)
    return bytes(data)


def read_varint(stream):
    value = 0
    for shift in range(0, 35, 7):
        byte = exact(stream, 1)[0]
        if shift == 28:
            check(not byte & 0xf0, "VarInt overflow or excessive length")
        value |= (byte & 0x7f) << shift
        if not byte & 0x80:
            return value - (1 << 32) if value & (1 << 31) else value
    raise ValueError("VarInt too long")


def string(value):
    encoded = value.encode("utf-8")
    return varint(len(encoded)) + encoded


def read_string(stream):
    size = read_varint(stream)
    check(0 <= size <= MAX_BODY, "Invalid string byte length")
    return exact(stream, size).decode("utf-8")


def short_array(stream):
    size = struct.unpack(">h", exact(stream, 2))[0]
    check(size >= 0, "Negative Short byte-array length")
    return exact(stream, size)


def finish(stream):
    check(stream.read() == b"", "Trailing payload bytes")


def frame(packet_id, payload=b""):
    body = varint(packet_id) + payload
    return varint(len(body)) + body


def send(sock, packet_id, payload=b""):
    data = frame(packet_id, payload)
    sock.sendall(data)
    print(f"TX id=0x{packet_id:02x} frame={data.hex(' ')}")


def receive(stream):
    size = read_varint(stream)
    check(1 <= size <= MAX_BODY, "Invalid packet body length")
    body = io.BytesIO(exact(stream, size))
    packet_id = read_varint(body)
    check(packet_id >= 0, "Negative packet ID")
    print(f"RX id=0x{packet_id:02x} body_length={size}")
    return packet_id, body


def handshake(host, port, state, protocol=5):
    check(state in (1, 2), "Unsupported next state")
    return varint(protocol) + string(host) + struct.pack(">H", port) + varint(state)


def encryption_request(body):
    server_id = read_string(body)
    public_key = short_array(body)
    token = short_array(body)
    finish(body)
    check(bool(public_key) and bool(token), "Empty encryption-request array")
    return dict(server_id=server_id, public_key_length=len(public_key),
                verify_token_length=len(token))


def login_success(body):
    raw_uuid, username = read_string(body), read_string(body)
    finish(body)
    uuid.UUID(raw_uuid)  # Syntax only, not identity or offline-algorithm validation.
    return username


def join_game(body):
    values = struct.unpack(">iBbBB", exact(body, 8))
    level_type = read_string(body)
    finish(body)
    result = dict(zip(("entity_id", "game_mode", "dimension", "difficulty",
                       "max_players"), values))
    result["level_type"] = level_type
    return result


def probe(mode, host, port, protocol=5):
    with socket.create_connection((host, port), timeout=5) as sock:
        sock.settimeout(5)
        with sock.makefile("rb") as stream:
            send(sock, 0, handshake(host, port, 1 if mode == "status" else 2, protocol))
            if mode != "reject":
                send(sock, 0, b"" if mode == "status" else string("S04Probe"))
            packet_id, body = receive(stream)
            if mode == "reject":
                check(packet_id == 0, "Expected Login Disconnect after Handshake")
                reason = json.loads(read_string(body))
                finish(body)
                expected = {4: "Outdated client! Please use 1.7.10",
                            6: "Outdated server! I'm still on 1.7.10"}
                print("DISCONNECT:", json.dumps(reason, ensure_ascii=True))
                check(reason == expected[protocol], "Unexpected version rejection reason")
            elif mode == "status":
                check(packet_id == 0, "Expected Status Response 0x00")
                status = json.loads(read_string(body))
                finish(body)
                print(json.dumps(status, ensure_ascii=True, indent=2))
                check(status["version"]["protocol"] == 5, "Server protocol is not 5")
                token = 0x0102030405060708
                send(sock, 1, struct.pack(">q", token))
                packet_id, body = receive(stream)
                check(packet_id == 1, "Expected Pong 0x01")
                check(struct.unpack(">q", exact(body, 8))[0] == token, "Pong mismatch")
                finish(body)
            else:
                if packet_id == 0:
                    reason = read_string(body)
                    finish(body)
                    raise ValueError("Login disconnected: " + reason)
                if mode == "online":
                    check(packet_id == 1, "Expected Encryption Request 0x01")
                    print(json.dumps(encryption_request(body), indent=2))
                    print("No Encryption Response sent; authentication untested.")
                else:
                    check(packet_id == 2, "Expected offline Login Success 0x02")
                    check(login_success(body) == "S04Probe", "Unexpected username")
                    print("LOGIN SUCCESS: UUID syntax valid; username=S04Probe")
                    packet_id, body = receive(stream)
                    check(packet_id == 1, "Expected Play Join Game 0x01")
                    print(json.dumps(join_game(body), indent=2))
    print(f"PASS: {mode} initial exchange; sent protocol={protocol}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("status", "online", "offline", "reject"))
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=25565)
    args = parser.parse_args()
    try:
        for protocol in ((4, 6) if args.mode == "reject" else (5,)):
            probe(args.mode, args.host, args.port, protocol)
    except (OSError, EOFError, ValueError, KeyError, TypeError, struct.error) as exc:
        parser.exit(1, f"FAIL: {exc}\n")


if __name__ == "__main__":
    main()
