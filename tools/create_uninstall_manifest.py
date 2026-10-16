"""Generate explicit NSIS delete instructions for a verified payload."""
from pathlib import Path
import sys

root=Path(sys.argv[1]).resolve();output=Path(sys.argv[2])
def escaped(relative):
    return str(relative).replace('$','$$').replace('"','$\\"')
files=sorted(p for p in root.rglob('*') if p.is_file())
directories=sorted((p for p in root.rglob('*') if p.is_dir()),key=lambda p:len(p.parts),reverse=True)
lines=[]
for p in files:
    if p.is_symlink() or not p.resolve().is_relative_to(root):raise ValueError('Payload contains a linked file')
    lines.append('Delete "$INSTDIR\\'+escaped(p.relative_to(root))+'"')
for p in directories:
    if p.is_symlink() or not p.resolve().is_relative_to(root):raise ValueError('Payload contains a linked folder')
    lines.append('RMDir "$INSTDIR\\'+escaped(p.relative_to(root))+'"')
output.write_text('\n'.join(lines)+'\n',encoding='utf-8')
print(f'Uninstall manifest: {len(files)} files, {len(directories)} directories')
