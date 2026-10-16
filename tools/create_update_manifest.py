"""Create public update metadata from the final (optionally signed) executable."""
import argparse
import hashlib
import json
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from release_updates import APP_VERSION, validate_manifest

def create_manifest(artifact, download_url, version=APP_VERSION, notes=''):
    path = Path(artifact)
    if not path.is_file() or path.suffix.lower() != '.exe' or path.stat().st_size == 0:
        raise ValueError('A nonempty final .exe artifact is required.')
    data = dict(schema_version=1, version=version, download_url=download_url, notes=notes)
    validate_manifest(data)
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
    data.update(sha256=digest.hexdigest(), size_bytes=path.stat().st_size)
    return data

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('artifact', type=Path)
    parser.add_argument('--download-url', required=True)
    parser.add_argument('--version', default=APP_VERSION)
    parser.add_argument('--notes-file', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    notes = args.notes_file.read_text(encoding='utf-8') if args.notes_file else ''
    data = create_manifest(args.artifact, args.download_url, args.version, notes)
    args.output.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')

if __name__ == '__main__':
    main()
