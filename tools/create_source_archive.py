"""Create a source-only ZIP without generated builds or user state."""
from pathlib import Path
import hashlib
import json
import sys
import zipfile


def main():
    root=Path(__file__).resolve().parents[1]
    output=Path(sys.argv[1]).resolve() if len(sys.argv)>1 else root/'dist'/'OrvantaVideoDownloader-Source.zip'
    extensions={'.py','.ps1','.bat','.sh','.spec','.txt','.lock','.md','.sha256','.nsi','.nsh'}
    paths=[p for p in root.iterdir() if p.is_file() and (p.suffix.lower() in extensions or p.name in {'.gitignore','.gitattributes'})]
    for directory in ('assets','browser-extension','tests','tools'):
        for p in (root/directory).rglob('*'):
            if not p.is_file() or '__pycache__' in p.parts or 'vendor' in p.parts or (directory=='tools' and 'diagnostics' in p.parts):continue
            allowed=extensions|({'.png','.ico','.svg','.js','.json','.css','.html'} if directory in ('assets','browser-extension','tests') else set())
            if p.suffix.lower() in allowed:paths.append(p)
    paths.append(root/'docs'/'PROJECT-LAYOUT.md')
    paths.append(root/'docs'/'BRANDING.md')
    paths.extend((root/'docs'/'screenshots').glob('orvanta-*.png'))
    paths.extend((root/'docs'/'releases').glob('*.md'))
    paths.extend((root/'docs'/'reports').glob('performance-*.md'))
    paths.extend((root/'docs'/'reports').glob('performance-*.json'))
    paths.extend((root/'docs'/'reports').glob('unified-setup-*.md'))
    paths=sorted(set(p for p in paths if p.is_file()))
    output.parent.mkdir(parents=True,exist_ok=True)
    manifest={p.relative_to(root).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
    with zipfile.ZipFile(output,'w',zipfile.ZIP_DEFLATED) as archive:
        for p in paths:archive.write(p,'video-downloader-desktop/'+p.relative_to(root).as_posix())
        archive.writestr('video-downloader-desktop/SOURCE-MANIFEST.json',json.dumps(manifest,indent=2))
    with zipfile.ZipFile(output) as archive:
        assert archive.testzip() is None
        for relative,digest in manifest.items():
            assert hashlib.sha256(archive.read('video-downloader-desktop/'+relative)).hexdigest()==digest
    print(f'Verified {len(paths)} source files: {output} ({output.stat().st_size:,} bytes)')


if __name__=='__main__':main()
