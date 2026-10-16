from pathlib import Path
from unittest.mock import patch
import pytest
from download_safety import apply_waiting_defaults, set_connection_mode, destinations_conflict


def job(root, url='https://youtu.be/first', template='%(title)s [%(id)s].%(ext)s'):
    return dict(url=url, config=dict(outdir=str(root), connection_mode='multiple', connections=4,
        template=template, mode='video', container='original', quality='best', audio_format='mp3', bitrate='192'),
        percent=50, downloaded=123, total=246)


def sparse(item, root):
    target = root / 'clip.mp4'
    item['transfer_files'] = [str(target)]
    Path(str(target) + '.part').write_bytes(b'partial')
    Path(str(target) + '.part.aria2').write_bytes(b'control')


def test_bulk_preserves_sparse_files_before_changing_directory(tmp_path):
    old = tmp_path / 'old'; old.mkdir()
    item = job(old); sparse(item, old)
    defaults = dict(item['config'], outdir=str(tmp_path / 'new'), connection_mode='single')
    assert apply_waiting_defaults(item, defaults) == 1
    assert [p.read_bytes() for p in old.glob('*.part.multi-backup-*')] == [b'partial']
    assert [p.read_bytes() for p in old.glob('*.aria2.multi-backup-*')] == [b'control']
    assert item['config']['outdir'] == defaults['outdir']
    assert (item['percent'], item['downloaded'], item['total']) == (0, 0, None)


def test_failed_control_backup_rolls_back_and_keeps_mode(tmp_path):
    item = job(tmp_path); sparse(item, tmp_path)
    original = Path.rename
    def rename(path, target):
        if str(path).endswith('.aria2'): raise OSError('locked')
        return original(path, target)
    with patch.object(Path, 'rename', rename), pytest.raises(OSError):
        set_connection_mode(item, 'single')
    assert item['config']['connection_mode'] == 'multiple'
    assert (tmp_path / 'clip.mp4.part').read_bytes() == b'partial'


def test_outside_directory_is_untouched(tmp_path):
    outside = tmp_path / 'outside'; outside.mkdir()
    root = tmp_path / 'root'; root.mkdir()
    item = job(root); sparse(item, outside)
    assert set_connection_mode(item, 'single') == 0
    assert (outside / 'clip.mp4.part').exists()


@pytest.mark.parametrize('template', ['video.%(ext)s', '%(title)s.%(ext)s', '%(id).4s.%(ext)s'])
def test_ambiguous_templates_serialize(tmp_path, template):
    assert destinations_conflict(job(tmp_path, template=template), job(tmp_path, 'https://youtu.be/second', template))


def test_youtube_aliases_exclude_each_other(tmp_path):
    assert destinations_conflict(job(tmp_path), job(tmp_path, 'https://www.youtube.com/watch?list=x&v=first'))
    assert not destinations_conflict(job(tmp_path), job(tmp_path, 'https://youtube.com/shorts/second'))


def test_unknown_identity_and_different_templates_serialize(tmp_path):
    assert destinations_conflict(job(tmp_path, 'https://a.test/a.mp4'), job(tmp_path, 'https://b.test/b.mp4'))
    assert destinations_conflict(job(tmp_path), job(tmp_path, template='%(id)s.%(ext)s'))


def test_distinct_output_directories_allow_concurrency(tmp_path):
    assert not destinations_conflict(job(tmp_path / 'one'), job(tmp_path / 'two'))


def test_escaped_identity_and_case_aliases_serialize(tmp_path):
    template = '%%(id)s.%(ext)s'
    assert destinations_conflict(job(tmp_path, template=template), job(tmp_path, 'https://youtu.be/second', template))
    assert destinations_conflict(job(tmp_path), job(tmp_path, 'https://youtu.be/FIRST'))


def test_inspected_ids_preserve_multisite_parallelism(tmp_path):
    left = job(tmp_path, 'https://a.test/watch/123'); left['video_id'] = '123'
    right = job(tmp_path, 'https://b.test/watch/456'); right['video_id'] = '456'
    assert not destinations_conflict(left, right)
    right['video_id'] = '123'
    assert destinations_conflict(left, right)
    right['video_id'] = 'unsafe/id'
    assert destinations_conflict(left, right)
