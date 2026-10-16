from copy import deepcopy
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QTreeWidgetItem
from app import Window,Store,DEFAULTS
from playlist_ui import NumberingControls,numbered_template
from test_process import app
from test_ui_performance import job,finish


def playlist(w,prefix='course'):
    w.playlist_title='Course';w.items=[dict(index=i,id=f'{prefix}-{i}',title='Lesson '+str(i),url=f'https://example.com/{prefix}/{i}') for i in (1,3)]
    for item in w.items:
        row=QTreeWidgetItem([item['title']]);row.setCheckState(0,Qt.Checked);w.pick.addTopLevelItem(row)
    w.enqueue()


def test_live_example_and_two_three_digit_toggle(tmp_path):
    w=Window(Store(tmp_path));control=NumberingControls(w,False,2)
    assert not control.style.isEnabled() and not control.preview.text().startswith('01')
    control.enabled.setChecked(True);assert control.preview.text().startswith('01 - ')
    control.style.setCurrentIndex(1);assert control.preview.text().startswith('001 - ')
    control.enabled.setChecked(False);assert not control.preview.text().startswith('001')
    assert numbered_template('title',123,2)=='123 - title'
    control.deleteLater();finish(w)


def test_saved_setting_automatically_prefixes_new_playlists(tmp_path):
    w=Window(Store(tmp_path));base=w.config()['template']
    w.checks['playlist_numbering'].setChecked(True);w.playlist_digits.setCurrentIndex(0)
    assert w.save_settings();playlist(w)
    assert [j['config']['template'] for j in w.jobs]==['01 - '+base,'03 - '+base]
    assert w.config()['template']==base
    w.playlist_digits.setCurrentIndex(1);assert w.save_settings();playlist(w,'second')
    assert [j['config']['template'] for j in w.jobs[2:]]==['001 - '+base,'003 - '+base]
    assert Store(tmp_path).data['settings']['playlist_digits']==3
    finish(w)


def test_defaults_never_rewrite_existing_queue(tmp_path):
    w=Window(Store(tmp_path));records=[job(i) for i in range(3)]
    for record,status in zip(records,['ready','paused','done']):record['status']=status
    w.jobs.extend(records);w.refresh_queue();before=deepcopy(w.jobs)
    w.open_preferences();w.checks['playlist_numbering'].setChecked(True);w.playlist_digits.setCurrentIndex(1)
    assert w.save_settings();w.cancel_preferences()
    assert w.jobs==before and Store(tmp_path).data['queue']==before
    finish(w)


def test_single_videos_are_not_prefixed(tmp_path):
    w=Window(Store(tmp_path));base=w.config()['template'];w.checks['playlist_numbering'].setChecked(True)
    w.playlist_title=None;w.items=[dict(id='single',title='Single',url='https://example.com/single')]
    row=QTreeWidgetItem(['Single']);row.setCheckState(0,Qt.Checked);w.pick.addTopLevelItem(row);w.enqueue()
    assert w.jobs[0]['config']['template']==base
    finish(w)


def test_settings_cancel_restores_numbering_style(tmp_path):
    w=Window(Store(tmp_path));w.open_preferences();w.playlist_digits.setCurrentIndex(1);w.checks['playlist_numbering'].setChecked(True)
    w.cancel_preferences();assert w.playlist_digits.currentData()==2 and not w.checks['playlist_numbering'].isChecked()
    finish(w)


def test_no_per_playlist_toolbar_or_menu_application(tmp_path):
    w=Window(Store(tmp_path));playlist(w)
    assert not hasattr(w,'playlist_options_btn')
    for item in w._queue_items.values():item.setSelected(True)
    menu=w.create_row_menu(w.queue.visualItemRect(w.queue.topLevelItem(0)).center())
    assert not any('number' in action.text().lower() for action in menu.actions())
    finish(w)


def test_previously_numbered_queue_is_preserved(tmp_path):
    store=Store(tmp_path);record=job(0);original='001 - '+DEFAULTS['template']
    record['config'].update(playlist_numbering=True,playlist_digits=3,template=original)
    record.update(playlist_template=DEFAULTS['template'],playlist_index=1,playlist_title='Old course')
    store.data['queue'].append(record);store.save()
    w=Window(Store(tmp_path));w.checks['playlist_numbering'].setChecked(False);assert w.save_settings()
    assert w.jobs[0]['config']['template']==original
    assert Store(tmp_path).data['queue'][0]['config']['template']==original
    finish(w)
