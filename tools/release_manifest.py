"""Record local release evidence; this is a builder snapshot, not a universal lock."""
import argparse
import hashlib
from importlib import metadata
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[1]


def file_record(path):
    path = Path(path).resolve()
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
    return {'path': str(path), 'bytes': path.stat().st_size, 'sha256': digest.hexdigest()}


def tool_record(path):
    record = file_record(path)
    # QuickJS prints its version with help; ffmpeg uses a single dash.
    name = Path(path).stem.lower()
    flag = '--help' if name == 'qjs' else '-version' if name in ('ffmpeg', 'ffprobe') else '--version'
    try:
        result = subprocess.run([str(Path(path).resolve()), flag], capture_output=True,
                                text=True, encoding='utf-8', errors='replace', timeout=15)
        record.update(version_output=(result.stdout + result.stderr)[:4096], version_returncode=result.returncode)
    except (OSError, subprocess.TimeoutExpired) as exc:
        record['version_error'] = str(exc)
    return record


def create_manifest(executable, root=ROOT):
    root = Path(root)
    sources = set(root.glob('*.py')) | set(root.glob('*.spec'))
    sources |= set((root / 'tools').glob('*.py'))
    sources |= {p for p in (root / 'assets').rglob('*') if p.is_file()}
    sources |= {p for p in root.glob('requirements*') if p.is_file()}
    sources.add(root / 'build.bat')
    source_hashes = {str(p.relative_to(root)): file_record(p)['sha256'] for p in sorted(sources) if p.is_file()}
    tools = {}
    for name, env, default in [('ffmpeg', 'VD_FFMPEG', 'tools/media/ffmpeg.exe'),
                               ('ffprobe', 'VD_FFPROBE', 'tools/media/ffprobe.exe'),
                               ('javascript', 'VD_JSBIN', 'tools/qjs.exe'),
                               ('aria2c', 'VD_ARIA', 'tools/aria2c.exe')]:
        path = Path(os.environ.get(env) or root / default)
        tools[name] = tool_record(path) if path.is_file() else {'path': str(path), 'missing': True}
    return {'schema_version': 1, 'created_utc': datetime.now(timezone.utc).isoformat(),
            'scope': 'Local builder snapshot; dependency versions are not a cross-platform lock.',
            'platform': platform.platform(), 'python': sys.version,
            'artifact': file_record(executable), 'source_sha256': source_hashes,
            'tools': tools, 'installed_dependencies': dict(sorted(
                (d.metadata['Name'], d.version) for d in metadata.distributions() if d.metadata['Name']))}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('executable', type=Path)
    args = parser.parse_args()
    output = Path(str(args.executable) + '.manifest.json')
    output.write_text(json.dumps(create_manifest(args.executable), indent=2) + '\n', encoding='utf-8')
    print(f'Release manifest: {output}')


if __name__ == '__main__':
    main()
