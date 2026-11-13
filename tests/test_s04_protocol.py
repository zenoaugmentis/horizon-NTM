"""Synthetic checks of the new probe, not evidence of Mojang server behavior."""
import importlib.util
import io
import json
from pathlib import Path
import struct
import unittest
from unittest import mock

SPEC = importlib.util.spec_from_file_location(
    "s04", Path(__file__).resolve().parents[1] / "tools" / "probe_s04.py")
p = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(p)


class Fragmented(io.BytesIO):
    def read(self, size=-1):
        return super().read(min(size, 1) if size >= 0 else size)


class ProtocolTests(unittest.TestCase):
    def test_probe_modes_with_synthetic_peer(self):
        class Peer:
            def __init__(self, incoming):
                self.incoming = incoming
                self.sent = bytearray()
            def __enter__(self):
                return self
            def __exit__(self, *args):
                pass
            def settimeout(self, value):
                pass
            def makefile(self, mode):
                return Fragmented(self.incoming)
            def sendall(self, data):
                self.sent.extend(data)

        status = p.frame(0, p.string('{"version":{"protocol":5}}'))
        pong = p.frame(1, bytes(range(1, 9)))
        encryption = p.frame(1, b"\x00\x00\x01K\x00\x04TEST")
        success = p.frame(2, p.string("00000000-0000-0000-0000-000000000000")
                          + p.string("S04Probe"))
        join = p.frame(1, bytes.fromhex("00 00 01 22 00 00 01 14 07") + b"default")
        cases = [("status", 5, status + pong), ("online", 5, encryption),
                 ("offline", 5, success + join)]
        for version, text in ((4, "Outdated client! Please use 1.7.10"),
                              (6, "Outdated server! I'm still on 1.7.10")):
            cases.append(("reject", version, p.frame(0, p.string(json.dumps(text)))))
        for mode, version, incoming in cases:
            with self.subTest(mode=mode, version=version):
                peer = Peer(incoming)
                with mock.patch.object(p.socket, "create_connection", return_value=peer), mock.patch("builtins.print"):
                    p.probe(mode, "127.0.0.1", 25565, version)
                sent = io.BytesIO(peer.sent)
                packet_id, body = p.receive(sent)
                self.assertEqual(packet_id, 0)
                self.assertEqual(body.read(), p.handshake("127.0.0.1", 25565,
                                                         1 if mode == "status" else 2, version))
                if mode != "reject":
                    packet_id, body = p.receive(sent)
                    self.assertEqual(packet_id, 0)
                    self.assertEqual(body.read(), b"" if mode == "status" else p.string("S04Probe"))
                if mode == "status":
                    packet_id, body = p.receive(sent)
                    self.assertEqual(packet_id, 1)
                    self.assertEqual(body.read(), bytes(range(1, 9)))
                self.assertEqual(sent.read(), b"")

    def test_handshake_literal_vectors(self):
        prefix = "0f 00 05 09 31 32 37 2e 30 2e 30 2e 31 63 dd "
        for state in (1, 2):
            self.assertEqual(p.frame(0, p.handshake("127.0.0.1", 25565, state)),
                             bytes.fromhex(prefix + f"{state:02x}"))

    def test_version_rejection_frames_and_json_string(self):
        for version, text in ((4, "Outdated client! Please use 1.7.10"),
                              (6, "Outdated server! I'm still on 1.7.10")):
            expected = bytes.fromhex(
                f"0f 00 {version:02x} 09 31 32 37 2e 30 2e 30 2e 31 63 dd 02")
            self.assertEqual(p.frame(0, p.handshake("127.0.0.1", 25565, 2, version)), expected)
            # Equivalent JSON may escape the apostrophe; raw server JSON was not logged.
            for json_text in (json.dumps(text), json.dumps(text).replace("'", r"\u0027")):
                payload = p.string(json_text)
                packet_id, body = p.receive(io.BytesIO(p.frame(0, payload)))
                self.assertEqual(packet_id, 0)
                self.assertEqual(json.loads(p.read_string(body)), text)
                p.finish(body)

    def test_status_ping_literal_vectors(self):
        self.assertEqual(p.frame(0), b"\x01\x00")
        self.assertEqual(p.frame(1, struct.pack(">q", 0x0102030405060708)),
                         bytes.fromhex("09 01 01 02 03 04 05 06 07 08"))

    def test_signed_varint_and_bounds(self):
        for value in (0, 127, 128, 255, 2147483647, -1, -2147483648):
            self.assertEqual(p.read_varint(io.BytesIO(p.varint(value))), value)
        self.assertEqual(p.varint(-1), bytes.fromhex("ff ff ff ff 0f"))
        for raw in (b"\x80" * 6, bytes.fromhex("ff ff ff ff 10")):
            with self.assertRaises(ValueError):
                p.read_varint(io.BytesIO(raw))

    def test_fragmentation_and_coalesced_packets(self):
        stream = Fragmented(bytes.fromhex("01 00 09 01 01 02 03 04 05 06 07 08"))
        packet_id, body = p.receive(stream)
        self.assertEqual(packet_id, 0)
        p.finish(body)
        packet_id, body = p.receive(stream)
        self.assertEqual(packet_id, 1)
        self.assertEqual(p.exact(body, 8), bytes(range(1, 9)))
        p.finish(body)

    def test_invalid_lengths_and_truncation(self):
        for raw in (b"\x00", p.varint(-1), p.varint(p.MAX_BODY + 1)):
            with self.assertRaises(ValueError):
                p.receive(io.BytesIO(raw))
        with self.assertRaises(EOFError):
            p.receive(io.BytesIO(b"\x02\x00"))
        with self.assertRaises(ValueError):
            p.short_array(io.BytesIO(b"\xff\xff"))
        with self.assertRaises(ValueError):
            p.read_string(io.BytesIO(p.varint(-1)))

    def test_encryption_short_array_lengths(self):
        # Synthetic arrays, not a cryptographic key/token or historical capture.
        raw = b"\x00\x00\xa2" + b"K" * 162 + b"\x00\x04" + b"TEST"
        result = p.encryption_request(io.BytesIO(raw))
        self.assertEqual(result, {"server_id": "", "public_key_length": 162,
                                  "verify_token_length": 4})
        with self.assertRaises(ValueError):
            p.encryption_request(io.BytesIO(raw + b"X"))

    def test_login_success_syntax_and_trailing(self):
        raw = p.string("00000000-0000-0000-0000-000000000000") + p.string("S04Probe")
        self.assertEqual(p.login_success(io.BytesIO(raw)), "S04Probe")
        with self.assertRaises(ValueError):
            p.login_success(io.BytesIO(raw + b"X"))
        with self.assertRaises(ValueError):
            p.login_success(io.BytesIO(p.string("invalid") + p.string("S04Probe")))

    def test_join_game_dimension_and_trailing(self):
        raw = bytes.fromhex("00 00 01 22 00 ff 01 14 07") + b"default"
        self.assertEqual(p.join_game(io.BytesIO(raw)),
                         {"entity_id": 290, "game_mode": 0, "dimension": -1,
                          "difficulty": 1, "max_players": 20, "level_type": "default"})
        with self.assertRaises(ValueError):
            p.join_game(io.BytesIO(raw + b"X"))


if __name__ == "__main__":
    unittest.main()
