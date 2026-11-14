import importlib.util
import json
from pathlib import Path
import struct
import tempfile
import unittest
import zipfile
import zlib

spec = importlib.util.spec_from_file_location('probe_s05', Path(__file__).resolve().parents[1] / 'tools' / 'probe_s05.py')
probe = importlib.util.module_from_spec(spec)
spec.loader.exec_module(probe)


def decode(data):
    assert data[:8] == b'\x89PNG\r\n\x1a\n'
    pos, compressed, dimensions = 8, b'', None
    while pos < len(data):
        size = struct.unpack('>I', data[pos:pos + 4])[0]
        kind = data[pos + 4:pos + 8]
        body = data[pos + 8:pos + 8 + size]
        crc = struct.unpack('>I', data[pos + 8 + size:pos + 12 + size])[0]
        assert crc == zlib.crc32(kind + body) & 0xffffffff
        if kind == b'IHDR':
            dimensions = struct.unpack('>IIBBBBB', body)
        if kind == b'IDAT':
            compressed += body
        pos += 12 + size
    assert dimensions[2:] == (8, 6, 0, 0, 0)
    width, height = dimensions[:2]
    rows = zlib.decompress(compressed)
    assert len(rows) == height * (1 + width * 4)
    return width, height, [rows[y * (1 + width * 4) + 1:(y + 1) * (1 + width * 4)] for y in range(height)]


class ProbeTests(unittest.TestCase):
    def test_pack_pixels_metadata_and_isolation(self):
        with tempfile.TemporaryDirectory() as temp:
            good, broken = probe.make_packs(Path(temp))
            with zipfile.ZipFile(good) as archive:
                self.assertEqual(len(archive.namelist()), 4)
                self.assertEqual(json.loads(archive.read('pack.mcmeta'))['pack']['pack_format'], 1)
                w, h, rows = decode(archive.read(probe.ITEMS + 'apple.png'))
                self.assertEqual((w, h), (16, 32))
                self.assertEqual(rows[:16], [bytes((255, 0, 0, 255)) * 16] * 16)
                self.assertEqual(rows[16:], [bytes((0, 255, 0, 255)) * 16] * 16)
                self.assertEqual(json.loads(archive.read(probe.ITEMS + 'apple.png.mcmeta')), {'animation': {'frametime': 10, 'frames': [0, 1]}})
                w, h, rows = decode(archive.read(probe.BLOCKS + 'stone.png'))
                self.assertEqual((w, h), (16, 16))
                self.assertEqual(rows[0][:4], bytes((0, 255, 255, 255)))
                self.assertEqual(rows[0][16:20], bytes((255, 0, 255, 255)))
            with zipfile.ZipFile(broken) as archive:
                self.assertEqual(set(archive.namelist()), {'pack.mcmeta', probe.BLOCKS + 'stone.png'})
                self.assertFalse(archive.read(probe.BLOCKS + 'stone.png').startswith(b'\x89PNG'))
            before = Path(good).read_bytes()
            with self.assertRaises(FileExistsError):
                probe.make_packs(Path(temp))
            self.assertEqual(before, Path(good).read_bytes())

    def test_extended_probes_and_folder_mutations(self):
        with tempfile.TemporaryDirectory() as temp:
            directory = Path(temp)
            paths = probe.make_extended(directory)
            self.assertEqual(len(paths), 14)
            for path in map(Path, paths):
                if path.suffix == '.zip':
                    with zipfile.ZipFile(path) as archive:
                        self.assertIsNone(archive.testzip())
                        self.assertIn('pack.mcmeta', archive.namelist())
                        for name in archive.namelist():
                            if name.endswith('.png'):
                                decode(archive.read(name))
            with zipfile.ZipFile(directory / 'S05-bad-animation-json.zip') as archive:
                with self.assertRaises(json.JSONDecodeError):
                    json.loads(archive.read(probe.ITEMS + 'apple.png.mcmeta'))
            with zipfile.ZipFile(directory / 'S05-bad-frame-index.zip') as archive:
                meta = json.loads(archive.read(probe.ITEMS + 'apple.png.mcmeta'))
                self.assertEqual(meta['animation']['frames'], [2])
            with zipfile.ZipFile(directory / 'S05-item-alpha.zip') as archive:
                _, _, rows = decode(archive.read(probe.ITEMS + 'apple.png'))
                self.assertEqual(rows[0][32:], bytes((0, 255, 0, 0)) * 8)
            folder = directory / 'S05-reload-folder'
            probe.mutate_folder(folder, 'stone-magenta')
            self.assertEqual(decode((folder / (probe.BLOCKS + 'stone.png')).read_bytes())[2][0], bytes((255, 0, 255, 255)) * 16)
            probe.mutate_folder(folder, 'apple-alpha128')
            rows = decode((folder / (probe.ITEMS + 'apple.png')).read_bytes())[2]
            self.assertEqual(rows[0][:32], bytes((255, 0, 0, 255)) * 8)
            self.assertEqual(rows[0][32:], bytes((255, 0, 0, 128)) * 8)
            tint = directory / 'S05-tint-folder'
            probe.mutate_folder(tint, 'grass-red')
            w, h, rows = decode((tint / 'assets/minecraft/textures/colormap/grass.png').read_bytes())
            self.assertEqual((w, h), (256, 256))
            self.assertEqual(rows, [bytes((255, 0, 0, 255)) * 256] * 256)
            before = (directory / 'S05-stack-A.zip').read_bytes()
            with self.assertRaises(FileExistsError):
                probe.make_extended(directory)
            self.assertEqual(before, (directory / 'S05-stack-A.zip').read_bytes())

    def test_inspection_missing_root_metadata_and_wrong_hash(self):
        with tempfile.TemporaryDirectory() as temp:
            jar = Path(temp) / 'synthetic.jar'
            with zipfile.ZipFile(jar, 'w') as archive:
                archive.writestr(probe.BLOCKS + 'sample.png', probe.png(16, 32, lambda x, y: (0, 0, 0, 255)))
                archive.writestr(probe.BLOCKS + 'sample.png.mcmeta', '{"animation":{}}')
            result = probe.inspect(jar)
            self.assertFalse(result['root_pack_mcmeta'])
            self.assertFalse(result['matches_s01'])
            self.assertEqual(result['counts'][probe.BLOCKS], {'.png': 1, '.mcmeta': 1})
            self.assertEqual(result['animations'][probe.BLOCKS + 'sample.png.mcmeta']['dimensions'], (16, 32))


if __name__ == '__main__':
    unittest.main()
