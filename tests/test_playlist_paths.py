from pathlib import Path
import pytest
from playlist_paths import playlist_directory
from app import Window,Store
from PySide6.QtWidgets import QTreeWidgetItem
from PySide6.QtCore import Qt,QCoreApplication,QEvent
from test_process import app


def test_safe_playlist_directory(tmp_path):
    for title in ['../escape','CON','My course: lesson / one','...','Arabic العربية']:
        target=Path(playlist_directory(tmp_path,'{playlist}',title))
        assert target.parent==tmp_path and target.name not in ('','.','..','CON')
    assert Path(playlist_directory(tmp_path,'Course - {playlist}','Python')).name=='Course - Python'
    with pytest.raises(ValueError):playlist_directory(tmp_path,'{unknown}','Video')


def test_playlist_folder_and_numbering_apply_only_to_playlist(tmp_path):
    w=Window(Store(tmp_path));w.folder.setText(str(tmp_path/'downloads'))
    w.checks['playlist_folders'].setChecked(True);w.playlist_folder_name.setText('Course - {playlist}')
    w.checks['playlist_numbering'].setChecked(True);w.playlist_title='Python: Basics'
    w.items=[dict(index=3,id='one',title='First',url='https://example.com/one')]
    row=QTreeWidgetItem(['First']);row.setCheckState(0,Qt.Checked);w.pick.addTopLevelItem(row);w.enqueue()
    cfg=w.jobs[0]['config'];assert Path(cfg['outdir']).name=='Course - Python_ Basics'
    assert cfg['template'].startswith('03 - ') and '%(id)s' in cfg['template']
    w.playlist_title=None;w.items=[dict(id='two',title='Single',url='https://example.com/two')]
    row=QTreeWidgetItem(['Single']);row.setCheckState(0,Qt.Checked);w.pick.addTopLevelItem(row);w.enqueue()
    assert w.jobs[1]['config']['outdir']==str(tmp_path/'downloads')
    assert not w.jobs[1]['config']['template'].startswith('001 - ')
    w.close();w.deleteLater();QCoreApplication.sendPostedEvents(None,QEvent.DeferredDelete)
