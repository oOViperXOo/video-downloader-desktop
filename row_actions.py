"""Context actions for queue and history records; never trust stale file paths."""
import errno
import os
from pathlib import Path
import shutil
import subprocess
import uuid
from urllib.parse import urlsplit

from PySide6.QtCore import Qt,QThread,Signal,QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QApplication,QFileDialog,QInputDialog,QMessageBox,QMenu

COMPLETED={'done','skipped'}
MEDIA={'.mp4','.webm','.mkv','.avi','.mov','.m4v','.flv','.wmv','.ts','.m2ts','.mpeg','.mpg','.ogv','.3gp','.vob','.mp3','.m4a','.aac','.wav','.flac','.ogg','.opus','.wma'}


def record_for_item(w,item):
    if item is None:return None
    key=item.data(0,Qt.UserRole)
    return next((r for r in w.jobs if r['id']==key),None) or next((r for r in w.history if 'history:'+str(id(r))==key),None)


def selected_records(w):
    return [r for item in w.queue.selectedItems() if (r:=record_for_item(w,item)) is not None]


def existing_file(record):
    try:
        if record.get('status') in COMPLETED:
            path=Path(record.get('path','')).expanduser()
            if path.is_file():return path
    except (OSError,ValueError):pass
    return None


def message(w,text):
    QMessageBox.information(w,'Download file',text)


def open_record(w,record):
    if record is None or record.get('status') not in COMPLETED:return
    path=existing_file(record)
    if path is None:message(w,'This downloaded file is no longer available. It may have been moved or deleted.');return
    try:
        if not QDesktopServices.openUrl(QUrl.fromLocalFile(str(path.absolute()))):message(w,'Could not open this file. Choose an app for its file type and try again.')
    except (OSError,ValueError) as exc:message(w,'Could not open the file: '+str(exc))


def show_in_folder(w,record):
    path=existing_file(record)
    if path is None:message(w,'This downloaded file is no longer available.');return
    try:
        if os.name=='nt':subprocess.Popen(['explorer.exe','/select,',str(path.absolute())],creationflags=subprocess.CREATE_NO_WINDOW)
        elif not QDesktopServices.openUrl(QUrl.fromLocalFile(str(path.absolute().parent))):message(w,'Could not open the folder.')
    except OSError as exc:message(w,'Could not open the folder: '+str(exc))


def in_use(w,path):
    target=os.path.normcase(os.path.abspath(path))
    task=getattr(w,'file_task',None)
    if task and task.isRunning() and any(target==os.path.normcase(os.path.abspath(p)) for pair in task.pairs for p in pair):return True
    return any(any(os.path.normcase(os.path.abspath(str(worker.job.get(key,''))))==target for key in ('path','_original_path','converted_path') if worker.job.get(key)) for worker in w.workers.values())


def editable_file(w,record):
    path=existing_file(record)
    return path if path is not None and not in_use(w,path) else None


def update_paths(w,source,destination):
    old=os.path.normcase(os.path.abspath(source))
    for record in [*w.jobs,*w.history]:
        for key in ('path','converted_path'):
            if record.get(key) and os.path.normcase(os.path.abspath(record[key]))==old:
                record[key]=str(destination)
                if key=='path' and Path(source).name!=destination.name:record['title']=destination.name
                if key=='path' and record in w.jobs:
                    record['config']['outdir']=str(destination.parent)
    w.store.save();w.refresh_history()


def move_without_overwrite(source,destination):
    """Exclusive destination creation; a failed copy leaves the source intact."""
    source,destination=Path(source),Path(destination)
    if not source.is_file():raise FileNotFoundError('The source file is no longer available.')
    if source.absolute()==destination.absolute():return
    if destination.exists():raise FileExistsError('A file with that name already exists.')
    try:
        if os.name=='nt':os.rename(source,destination)
        else:os.link(source,destination);source.unlink()
        return
    except OSError as exc:
        if exc.errno!=errno.EXDEV and getattr(exc,'winerror',None)!=17:raise
    created=False
    try:
        with source.open('rb') as src,destination.open('xb') as dst:
            created=True;shutil.copyfileobj(src,dst,1024*1024)
        shutil.copystat(source,destination)
        source.unlink()
    except OSError:
        if created:destination.unlink(missing_ok=True)
        raise


def rename_file(w,record):
    source=editable_file(w,record)
    if source is None:message(w,'The file is missing or currently in use.');return
    name,ok=QInputDialog.getText(w,'Rename file','File name:',text=source.name)
    if not ok:return
    name=name.strip()
    if not name or name in ('.','..') or any(c in name for c in '/\\:') or Path(name).name!=name:
        message(w,'Enter a file name without folders.');return
    destination=source.with_name(name)
    if in_use(w,source):message(w,'This file is currently in use.');return
    try:move_without_overwrite(source,destination)
    except OSError as exc:message(w,'Could not rename the file: '+str(exc));return
    update_paths(w,source,destination)


class FileMove(QThread):
    result=Signal(object)
    def __init__(self,pairs,parent):super().__init__(parent);self.pairs=pairs
    def run(self):
        moved=[];errors=[]
        for source,destination in self.pairs:
            try:move_without_overwrite(source,destination);moved.append((source,destination))
            except OSError as exc:errors.append(source.name+': '+str(exc))
        self.result.emit((moved,errors))


def move_files(w,records):
    if getattr(w,'file_task',None) and w.file_task.isRunning():return
    sources=[editable_file(w,r) for r in records]
    if not all(sources):message(w,'A selected file is missing or currently in use.');return
    directory=QFileDialog.getExistingDirectory(w,'Move files to',str(sources[0].parent))
    if not directory:return
    if any(in_use(w,source) for source in sources):message(w,'A selected file is currently in use.');return
    pairs=[(source,Path(directory)/source.name) for source in dict.fromkeys(sources)]
    task=FileMove(pairs,w);w.file_task=task
    w.file_task_pending=True
    for record in records:
        row=w.row_widgets.get(record.get('id'))
        if row:row.detail.setText('Moving file…');row._display_state=None
    def complete(result):
        moved,errors=result
        for source,destination in moved:update_paths(w,source,destination)
        w.file_task_pending=False
        for row in w.row_widgets.values():row.update_state()
        if errors:message(w,'Some files could not be moved:\n'+'\n'.join(errors))
    task.result.connect(complete);task.start()


def delete_files(w,records):
    sources=list(dict.fromkeys(editable_file(w,r) for r in records))
    if not sources or None in sources:message(w,'A selected file is missing or currently in use.');return
    text='Permanently delete '+str(len(sources))+' file(s) from disk and remove their download records?\n\n'+'\n'.join(str(p) for p in sources[:5])+'\n\nThis cannot be undone.'
    if QMessageBox.warning(w,'Delete file',text,QMessageBox.Yes|QMessageBox.No,QMessageBox.No)!=QMessageBox.Yes:return
    errors=[];deleted=set()
    for source in sources:
        try:
            if in_use(w,source):raise OSError('File is currently in use.')
            if not source.is_file():raise FileNotFoundError('File is no longer available.')
            source.unlink()
            deleted.add(os.path.normcase(os.path.abspath(source)))
        except OSError as exc:errors.append(source.name+': '+str(exc))
    def keep(record):
        return not (record.get('status') in COMPLETED and record.get('path') and
                    os.path.normcase(os.path.abspath(Path(record['path']).expanduser())) in deleted)
    w.jobs[:]=[record for record in w.jobs if keep(record)]
    w.history[:]=[record for record in w.history if keep(record)]
    w.store.save()
    w.refresh_history()
    if errors:message(w,'Some files could not be deleted:\n'+'\n'.join(errors))


def change_url(w,record):
    if record not in w.jobs or record.get('status') not in ('paused','error') or w.is_running(record):return
    value,ok=QInputDialog.getText(w,'Change URL','New video or direct download URL:\nStarts fresh; existing partial files are kept.',text=record.get('url',''))
    if not ok or value.strip()==record.get('url'):return
    value=value.strip()
    try:
        parsed=urlsplit(value)
        if parsed.scheme not in ('http','https') or not parsed.hostname or any(c.isspace() for c in value):raise ValueError()
    except ValueError:message(w,'Enter a valid HTTP or HTTPS URL.');return
    token=uuid.uuid4().hex[:8]
    record['config']['template']=record['config']['template'].replace('%(ext)s','link-'+token+'.%(ext)s')
    if record.get('playlist_template'):
        record['playlist_template']=record['playlist_template'].replace('%(ext)s','link-'+token+'.%(ext)s')
    record['config']['format_id']=''
    for key in ('path','video_id','source_id','source_extractor','duration','transfer_files','retry_at','retry_count','selected_format','formats','estimated_bytes','converted_path'):
        record.pop(key,None)
    record.update(url=value,title=value,status='ready',percent=0,downloaded=0,total=None,error='',speed='',eta='')
    w.store.save();w.refresh_history()


def build_menu(w,position):
    item=w.queue.itemAt(position)
    if item is not None and not item.isSelected():w.queue.setCurrentItem(item)
    records=selected_records(w);one=records[0] if len(records)==1 else None
    menu=QMenu(w.queue)
    if one is not None and one.get('status') in COMPLETED:
        action=menu.addAction('Open',lambda:open_record(w,one));action.setEnabled(existing_file(one) is not None)
        action=menu.addAction('Show in folder',lambda:show_in_folder(w,one));action.setEnabled(existing_file(one) is not None)
        menu.addSeparator()
    urls=list(dict.fromkeys(r.get('url','') for r in records if r.get('url')))
    if urls:
        menu.addAction('Copy link',lambda:QApplication.clipboard().setText('\n'.join(urls)))
        if one is not None:menu.addAction('Open download page',lambda:QDesktopServices.openUrl(QUrl(one['url'])))
    if one is not None and editable_file(w,one):menu.addAction('Rename file',lambda:rename_file(w,one))
    file_busy=bool(getattr(w,'file_task',None) and w.file_task.isRunning())
    if records and all(editable_file(w,r) for r in records) and not file_busy:
        menu.addAction('Move to…',lambda:move_files(w,records))
        menu.addAction('Delete file',lambda:delete_files(w,records))
    if one is not None and one in w.jobs and one.get('status') in ('paused','error') and not w.is_running(one):
        menu.addAction('Change URL',lambda:change_url(w,one))
    from features_ui import mp4_copy_candidate,convert_existing
    candidate=mp4_copy_candidate(w)
    if candidate is not None:menu.addAction('make MP4 copy',lambda:convert_existing(w,candidate))
    if one is not None and (path:=existing_file(one)) and path.suffix.lower() in MEDIA-{'.mp3'} and not in_use(w,path):
        menu.addAction('Make MP3 copy',lambda:convert_existing(w,one,'mp3'))
    if records:menu.addSeparator()
    action=menu.addAction('Remove from list',w.remove_selected_rows);action.setEnabled(bool(records))
    return menu
