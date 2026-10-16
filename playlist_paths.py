"""Safe, single-directory playlist naming for Windows downloads."""
import re
from pathlib import Path


def playlist_directory(root, template, title):
    template=template.strip()
    if not template or re.search(r'\{(?!playlist\})|(?<!playlist)\}',template):
        raise ValueError('Use {playlist} or plain text for the playlist folder name.')
    name=template.replace('{playlist}',title or 'Playlist')
    name=re.sub(r'[<>:"/\\|?*\x00-\x1f]','_',name).strip(' .')[:120].rstrip(' .')
    if not name:name='Playlist'
    if re.match(r'^(CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])(?:\.|$)',name,re.I):name='_'+name
    return str(Path(root).expanduser()/name)
