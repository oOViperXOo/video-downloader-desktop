"""Filename-prefix defaults for newly added playlists."""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QWidget,QCheckBox,QLabel,QFormLayout


def numbered_template(base,index,digits,enabled=True):
    return (f'{max(1,int(index)):0{2 if digits==2 else 3}d} - ' if enabled else '')+base



class NumberingControls(QWidget):
    def __init__(self,w,enabled,digits,title='Lesson title [video ID]',index=1):
        super().__init__();self.title=title;self.index=index
        form=QFormLayout(self);form.setContentsMargins(0,0,0,0)
        self.enabled=QCheckBox('Automatically prefix new playlist filenames');self.enabled.setObjectName('playlistNumbering');self.enabled.setChecked(enabled);form.addRow(self.enabled)
        self.style=w.combo(['01, 02, 03…','001, 002, 003…'],'01, 02, 03…' if digits==2 else '001, 002, 003…')
        self.style.setItemData(0,2);self.style.setItemData(1,3);self.style.setObjectName('playlistNumberingStyle');form.addRow('Number format',self.style)
        self.preview=QLabel();self.preview.setWordWrap(True);self.preview.setTextFormat(Qt.PlainText);self.preview.setObjectName('playlistNumberingPreview');form.addRow('Example filename',self.preview)
        self.enabled.toggled.connect(self.update_preview);self.style.currentIndexChanged.connect(self.update_preview);self.update_preview()

    def update_preview(self,*args):
        self.style.setEnabled(self.enabled.isChecked())
        self.preview.setText(numbered_template(self.title,self.index,self.style.currentData(),self.enabled.isChecked())+'.mp4')

