"""S05: inspect local JAR metadata or build original resource-pack probes. Python 3.10+."""
import argparse
import hashlib
import json
from pathlib import Path
import struct
import zipfile
import zlib

EXPECTED_SHA1 = 'e80d9b3bf5085002218d4be59e668bac718abbc6'
BLOCKS = 'assets/minecraft/textures/blocks/'
ITEMS = 'assets/minecraft/textures/items/'


def chunk(kind, data):
    return struct.pack('>I', len(data)) + kind + data + struct.pack('>I', zlib.crc32(kind + data) & 0xffffffff)


def png(width, height, pixels):
    rows = [bytes(pixels(x, y)) for y in range(height) for x in range(width)]
    stride = width * 4
    raw = b''.join(rows)
    scanlines = b''.join(b'\0' + raw[y * stride:(y + 1) * stride] for y in range(height))
    return b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB', width, height, 8, 6, 0, 0, 0)) + chunk(b'IDAT', zlib.compress(scanlines)) + chunk(b'IEND', b'')


def make_packs(directory):
    directory.mkdir(parents=True, exist_ok=True)
    good = directory / 'S05-probe-v1.zip'
    broken = directory / 'S05-probe-broken-v1.zip'
    # Refuse replacement of an existing user file; use a fresh directory for retries.
    for path in (good, broken):
        if path.exists():
            raise FileExistsError(path)
    with zipfile.ZipFile(good, 'x', zipfile.ZIP_DEFLATED) as archive:
        archive.writestr('pack.mcmeta', json.dumps({'pack': {'pack_format': 1, 'description': 'Horizon S05 original texture probe v1'}}))
        archive.writestr(BLOCKS + 'stone.png', png(16, 16, lambda x, y: (255, 0, 255, 255) if (x // 4 + y // 4) % 2 else (0, 255, 255, 255)))
        archive.writestr(ITEMS + 'apple.png', png(16, 32, lambda x, y: (255, 0, 0, 255) if y < 16 else (0, 255, 0, 255)))
        archive.writestr(ITEMS + 'apple.png.mcmeta', json.dumps({'animation': {'frametime': 10, 'frames': [0, 1]}}))
    with zipfile.ZipFile(broken, 'x', zipfile.ZIP_DEFLATED) as archive:
        archive.writestr('pack.mcmeta', json.dumps({'pack': {'pack_format': 1, 'description': 'Horizon S05 intentionally broken stone texture'}}))
        archive.writestr(BLOCKS + 'stone.png', b'S05 intentionally invalid PNG')
    return [str(good), str(broken)]


def make_extended(directory):
    """Recreate additional probes; these generated files were not run on the reference client."""
    directory.mkdir(parents=True, exist_ok=True)
    stone = BLOCKS + 'stone.png'
    apple = ITEMS + 'apple.png'
    meta = apple + '.mcmeta'
    solid = lambda color: png(16, 16, lambda x, y: color)
    base = {stone: solid((0, 255, 255, 255)),
            apple: png(16, 32, lambda x, y: (255, 0, 0, 255) if y < 16 else (0, 255, 0, 255))}
    variants = {
        'bad-animation-json': '{',
        'bad-frame-index': {'frametime': 10, 'frames': [2]},
        'frame-times': {'frametime': 20, 'frames': [{'index': 0, 'time': 10}, {'index': 1, 'time': 40}]},
        'frame-time-default': {'frametime': 40, 'frames': [{'index': 0, 'time': 10}, {'index': 1}]},
        'auto-frames': {'frametime': 20},
        'default-frametime': {'frames': [0] * 10 + [{'index': 1, 'time': 10}]},
        'zero-frametime': {'frametime': 0, 'frames': [0, 1]},
        'zero-frame-time': {'frametime': 20, 'frames': [{'index': 0, 'time': 0}, 1]},
    }
    packs = {}
    for name, animation in variants.items():
        packs['S05-' + name + '.zip'] = dict(base, **{meta: animation if isinstance(animation, str) else json.dumps({'animation': animation})})
    packs['S05-stack-A.zip'] = dict(base, **{meta: json.dumps({'animation': {'frametime': 10, 'frames': [0, 1]}})})
    packs['S05-stack-B.zip'] = {stone: solid((255, 255, 0, 255)), apple: solid((0, 0, 255, 255))}
    # Reproduction-only sidecar control; exact historical C metadata is unavailable.
    packs['S05-sidecar-control.zip'] = {meta: json.dumps({'animation': {'frametime': 40, 'frames': [1]}})}
    packs['S05-item-alpha.zip'] = {stone: base[stone], apple: png(16, 16, lambda x, y: (255, 0, 0, 255) if x < 8 else (0, 255, 0, 0))}
    paths = [directory / n for n in packs]
    folders = [directory / 'S05-reload-folder', directory / 'S05-tint-folder']
    for path in paths + folders:
        if path.exists():
            raise FileExistsError(path)
    def entries(name, files):
        return {'pack.mcmeta': json.dumps({'pack': {'pack_format': 1, 'description': name}}), **files}
    for name, files in packs.items():
        with zipfile.ZipFile(directory / name, 'x', zipfile.ZIP_DEFLATED) as archive:
            for key, data in entries(name, files).items():
                archive.writestr(key, data)
    folder_files = [packs['S05-stack-B.zip'], {stone: solid((255, 255, 255, 255)), BLOCKS + 'grass_top.png': solid((255, 255, 255, 255))}]
    for folder, files in zip(folders, folder_files):
        for key, data in entries(folder.name, files).items():
            target = folder / key
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data.encode() if isinstance(data, str) else data)
    return [str(p) for p in paths + folders]


def mutate_folder(directory, action):
    if not (directory / 'pack.mcmeta').is_file():
        raise FileNotFoundError('Expected generated folder pack: ' + str(directory))
    if action == 'stone-magenta':
        relative, data = BLOCKS + 'stone.png', png(16, 16, lambda x, y: (255, 0, 255, 255))
    elif action == 'apple-alpha128':
        relative, data = ITEMS + 'apple.png', png(16, 16, lambda x, y: (255, 0, 0, 255 if x < 8 else 128))
    else:
        relative, data = 'assets/minecraft/textures/colormap/grass.png', png(256, 256, lambda x, y: (255, 0, 0, 255))
    target = directory / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(data)
    return str(target)


def inspect(jar):
    digest = hashlib.sha1(jar.read_bytes()).hexdigest()
    result = {'sha1': digest, 'matches_s01': digest == EXPECTED_SHA1}
    with zipfile.ZipFile(jar) as archive:
        names = archive.namelist()
        result['root_pack_mcmeta'] = 'pack.mcmeta' in names
        result['counts'] = {p: {ext: sum(n.startswith(p) and n.endswith(ext) for n in names) for ext in ('.png', '.mcmeta')} for p in (BLOCKS, ITEMS)}
        result['modern_resource_counts'] = {p: sum(n.startswith(p) and not n.endswith('/') for n in names) for p in ('assets/minecraft/models/', 'assets/minecraft/blockstates/')}
        animations = {}
        for name in sorted(names):
            if name.startswith((BLOCKS, ITEMS)) and name.endswith('.png.mcmeta'):
                data = archive.read(name[:-7])
                if not data.startswith(b'\x89PNG\r\n\x1a\n') or len(data) < 24:
                    raise ValueError('Invalid PNG header: ' + name[:-7])
                animations[name] = {'dimensions': struct.unpack('>II', data[16:24]), 'metadata': json.loads(archive.read(name))}
        result['animations'] = animations
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    commands.add_parser('inspect').add_argument('--jar', required=True, type=Path)
    commands.add_parser('packs').add_argument('--output', required=True, type=Path)
    commands.add_parser('extended').add_argument('--output', required=True, type=Path)
    mutation = commands.add_parser('mutate')
    mutation.add_argument('--folder', required=True, type=Path)
    mutation.add_argument('--action', required=True, choices=['stone-magenta', 'apple-alpha128', 'grass-red'])
    args = parser.parse_args()
    if args.command == 'inspect':
        result = inspect(args.jar)
    elif args.command == 'packs':
        result = make_packs(args.output)
    elif args.command == 'extended':
        result = make_extended(args.output)
    else:
        result = mutate_folder(args.folder, args.action)
    print(json.dumps(result, indent=2, ensure_ascii=False))
    if args.command == 'inspect' and not result['matches_s01']:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
