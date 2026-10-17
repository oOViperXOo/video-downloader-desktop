import codecs,json
from PySide6.QtCore import Qt,QCoreApplication,QEvent
from PySide6.QtWidgets import QApplication
from app import Window,Store,DEFAULTS
from test_process import app
import engine


def finish(w):
    w.inspector=None;w.close();w.deleteLater();QCoreApplication.sendPostedEvents(None,QEvent.DeferredDelete)


def test_clipboard_updates_focused_inline_field_but_preserves_typed_draft(tmp_path):
    w=Window(Store(tmp_path));w.show();w.url.setFocus();app.processEvents()
    QApplication.clipboard().setText('https://youtu.be/abcdefghijk');app.processEvents()
    assert w.url.text()=='https://youtu.be/abcdefghijk' and w.url.isVisible() and not w.add_dialog.isVisible()
    QApplication.clipboard().setText('https://youtube.com/playlist?list=PLexample');app.processEvents()
    assert 'PLexample' in w.url.text()
    w.url.setText('https://example.com/draft');w.link_edited()
    QApplication.clipboard().setText('https://vimeo.com/1234');app.processEvents()
    assert w.url.text()=='https://example.com/draft'
    w.capture_copied_links(force=True);assert w.url.text()=='https://vimeo.com/1234'
    assert not hasattr(w,'queue_search') and all(not button.isVisible() for button in w.filter_buttons.values())
    finish(w)


def test_add_inspection_queues_single_and_playlist_without_modal(tmp_path,monkeypatch):
    class Process:
        def readAllStandardOutput(self):return b''
        def deleteLater(self):pass
    w=Window(Store(tmp_path));w.show()
    monkeypatch.setattr(w,'confirm_playlist',lambda *a:(_ for _ in ()).throw(AssertionError('Unexpected playlist dialog')))
    monkeypatch.setattr('features_ui.choose_formats',lambda *a:(_ for _ in ()).throw(AssertionError('Unexpected format dialog')))
    for identifiers in (['abcdefghijk'],['ABCDEFGHIJK','12345678901','ABCDEFGHIJK']):
        w.inspector=Process();w.inspection_cancelled=False;w.inspect_decoder=codecs.getincrementaldecoder('utf-8')()
        w.inspect_output=json.dumps({'title':'Playlist','items':[{'id':identity,'title':identity,'url':'https://www.youtube.com/watch?v='+identity,'formats':[{'height':720,'vcodec':'avc1'},{'height':360,'vcodec':'avc1'}]} for identity in identifiers]})
        w.inspected(0)
    assert len(w.jobs)==3 and all(j['status']=='ready' for j in w.jobs) and not w.workers
    row=w.row_widgets[w.jobs[0]['id']];assert row.quality.isVisible() and row.height()==44
    assert row.quality.maxVisibleItems()==8 and row.primary.text()=='Start' and w.start_all_btn.isVisible()
    row.quality.setCurrentText('720p');app.processEvents();assert w.jobs[0]['config']['quality']=='720'
    finish(w)


def test_watch_later_login_preflight_and_authenticated_playlist(monkeypatch):
    calls=[]
    monkeypatch.setattr(engine,'_run_json_lines',lambda args,timeout:calls.append(args) or [{'id':'abcdefghijk','url':'abcdefghijk','title':'Video','playlist_index':1}])
    import pytest
    with pytest.raises(engine.EngineError,match='logged-in browser'):engine.inspect_url('https://www.youtube.com/playlist?list=WL')
    assert not calls
    result=engine.inspect_url('https://www.youtube.com/playlist?list=WL',False,extra_args=['--cookies-from-browser','firefox'])
    assert result['is_playlist'] and result['items'][0]['url']=='https://www.youtube.com/watch?v=abcdefghijk'
    assert '--yes-playlist' in calls[0] and '--cookies-from-browser' in calls[0]


def test_canonical_playlist_share_links_and_login_cli(monkeypatch,capsys):
    target,identity=engine.inspection_target('https://www.youtube.com/watch?v=abcdefghijk&amp;list=PLExample&index=3')
    assert identity=='PLExample' and target=='https://www.youtube.com/playlist?list=PLExample'
    target,identity=engine.inspection_target('https://youtu.be/abcdefghijk?list=RDabcdefghijk')
    assert 'v=abcdefghijk' in target and identity=='RDabcdefghijk'
    calls=[];monkeypatch.setattr(engine,'inspect_url',lambda url,**kwargs:calls.append(kwargs) or {'items':[]})
    assert engine.main(['--inspect','https://www.youtube.com/playlist?list=WL','--cookies-from-browser','edge'])==0
    assert calls[0]['extra_args']==['--cookies-from-browser','edge']


def test_inspection_forwards_applied_browser_setting(tmp_path,monkeypatch):
    from PySide6.QtCore import QProcess
    w=Window(Store(tmp_path));w.cookies_browser.setCurrentText('firefox');w.url.setText('https://www.youtube.com/playlist?list=WL')
    calls=[];monkeypatch.setattr(w,'command',lambda process,args:calls.append(args))
    w.inspect();assert calls and calls[0][-2:]==['--cookies-from-browser','firefox']
    w.inspector.deleteLater();w.inspector=None;finish(w)

def test_row_quality_uses_own_formats_and_unknown_fallback(tmp_path):
    w=Window(Store(tmp_path))
    try:
        for index, heights in enumerate(([720,540,360],[480],[])):
            w.jobs.append({'id':str(index),'title':'Video','url':'https://example.com/'+str(index),
                           'config':dict(DEFAULTS),'status':'ready',
                           'formats':[{'height':height,'vcodec':'avc1'} for height in heights]})
        w.refresh_queue()
        for index,expected in enumerate((['720','540','360'],['480'],['best'])):
            combo=w.row_widgets[str(index)].quality
            assert [combo.itemData(i) for i in range(combo.count())]==expected
            assert w.jobs[index]['config']['quality']==expected[0]
        combo=w.row_widgets['0'].quality
        combo.setCurrentIndex(1);app.processEvents()
        assert w.jobs[0]['config']['quality']=='540'
        w.refresh_queue()
        assert w.jobs[0]['config']['quality']=='540'
    finally:
        finish(w)
