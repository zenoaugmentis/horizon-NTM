"""Synthetic crypto model only: no network, session service or real credentials."""
import hashlib
import io
import struct
import unittest
from test_s04_protocol import p

try:
    from cryptography.hazmat.primitives.asymmetric import padding, rsa
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.ciphers import Cipher, algorithms
    try:
        from cryptography.hazmat.decrepit.ciphers.modes import CFB8
    except ImportError:  # Older cryptography versions.
        from cryptography.hazmat.primitives.ciphers.modes import CFB8
    CRYPTO = True
except ImportError:
    CRYPTO = False


def signed_hex(digest):
    value = int.from_bytes(digest, "big", signed=True)
    return ("-" if value < 0 else "") + format(abs(value), "x")


class HashTests(unittest.TestCase):
    def test_signed_hex_boundaries(self):
        self.assertEqual(signed_hex(bytes(20)), "0")
        self.assertEqual(signed_hex(bytes(19) + b"\x01"), "1")
        self.assertEqual(signed_hex(b"\xff" * 20), "-1")
        self.assertEqual(signed_hex(b"\x80" + bytes(19)), "-8" + "0" * 39)

    def test_hash_concat_literal(self):
        # SHA-1('abc') from a fixed digest, split into three synthetic fields.
        digest = hashlib.sha1(b"a" + b"b" + b"c").digest()
        self.assertEqual(digest.hex(), "a9993e364706816aba3e25717850c26c9cd0d89d")
        self.assertEqual(signed_hex(digest), "-5666c1c9b8f97e9545c1da8e87af3d93632f2763")


@unittest.skipUnless(CRYPTO, "Optional cryptography package unavailable; crypto model NOT tested")
class CryptoModelTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.private_key = rsa.generate_private_key(public_exponent=65537, key_size=1024)
        cls.der = cls.private_key.public_key().public_bytes(
            serialization.Encoding.DER, serialization.PublicFormat.SubjectPublicKeyInfo)
        cls.secret = bytes(range(16))  # Synthetic fixed secret; never use in real login.
        cls.token = b"TEST"

    def response(self):
        pub = serialization.load_der_public_key(self.der)
        fields = [pub.encrypt(value, padding.PKCS1v15())
                  for value in (self.secret, self.token)]
        return p.frame(1, b"".join(struct.pack(">h", len(v)) + v for v in fields))

    def test_rsa_response_short_lengths_and_token(self):
        packet_id, body = p.receive(io.BytesIO(self.response()))
        self.assertEqual(packet_id, 1)
        secret_ct, token_ct = p.short_array(body), p.short_array(body)
        p.finish(body)
        self.assertEqual((len(secret_ct), len(token_ct)), (128, 128))
        secret = self.private_key.decrypt(secret_ct, padding.PKCS1v15())
        token = self.private_key.decrypt(token_ct, padding.PKCS1v15())
        self.assertEqual(secret, self.secret)
        self.assertEqual(token, self.token)
        self.assertNotEqual(token, b"FAIL")
        self.assertEqual(len(self.der), 162)

    def test_encryption_boundary_and_stream_fragmentation(self):
        # Synthetic Login Success + Join Game; no claim that this is authenticated.
        success = p.frame(2, p.string("00000000-0000-0000-0000-000000000000")
                          + p.string("S04Probe"))
        join = p.frame(1, bytes.fromhex("00 00 01 22 00 00 01 14 07") + b"default")
        plain = success + join
        enc = Cipher(algorithms.AES(self.secret), CFB8(self.secret)).encryptor()
        ciphertext = enc.update(success) + enc.update(join) + enc.finalize()
        whole = Cipher(algorithms.AES(self.secret), CFB8(self.secret)).encryptor()
        self.assertEqual(ciphertext, whole.update(plain) + whole.finalize())
        self.assertNotEqual(ciphertext, plain)

        response = self.response()
        wire = io.BytesIO(response + ciphertext)
        packet_id, body = p.receive(wire)  # Plaintext response ends before AES starts.
        self.assertEqual(packet_id, 1)
        secret_ct, token_ct = p.short_array(body), p.short_array(body)
        p.finish(body)
        secret = self.private_key.decrypt(secret_ct, padding.PKCS1v15())
        self.assertEqual(self.private_key.decrypt(token_ct, padding.PKCS1v15()), self.token)
        dec = Cipher(algorithms.AES(secret), CFB8(secret)).decryptor()
        decrypted = bytearray()
        while chunk := wire.read(3):
            decrypted.extend(dec.update(chunk))
        decrypted.extend(dec.finalize())
        self.assertEqual(bytes(decrypted), plain)
        packets = io.BytesIO(decrypted)
        packet_id, body = p.receive(packets)
        self.assertEqual(packet_id, 2)
        self.assertEqual(p.login_success(body), "S04Probe")
        packet_id, body = p.receive(packets)
        self.assertEqual(packet_id, 1)
        self.assertEqual(p.join_game(body)["dimension"], 0)
        self.assertEqual(packets.read(), b"")
        # Restarting state at a packet boundary must not reproduce the stream.
        restarted = Cipher(algorithms.AES(secret), CFB8(secret)).encryptor()
        self.assertNotEqual(ciphertext[len(success):], restarted.update(join))


if __name__ == "__main__":
    unittest.main()
