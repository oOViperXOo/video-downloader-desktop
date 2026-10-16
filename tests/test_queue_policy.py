from datetime import datetime
import pytest
from queue_policy import canonical_url,unique_links,retry_delay,schedule_allows,disk_space_required,check_disk_space


def test_batch_aliases_duplicates_invalid_and_original_urls():
    accepted,duplicates,invalid=unique_links('https://youtu.be/abc\nhttps://youtube.com/watch?v=abc&pp=x\nhttps://example.com/a.mp4\nfile:///private', ['https://example.com/a.mp4'])
    assert accepted==['https://youtu.be/abc'] and duplicates==2 and invalid==['file:///private']
    assert canonical_url('https://youtube.com/watch?v=A')!=canonical_url('https://youtube.com/watch?v=a')
    assert canonical_url('https://EXAMPLE.com:443/a#foo')==canonical_url('https://example.com/a')
    assert canonical_url('https://youtu.be/abc?list=PL1')==canonical_url('https://www.youtube.com/playlist?list=PL1')


@pytest.mark.parametrize('message',['Login required: connection failed','DRM protected','Unsupported URL','HTTP 404','No space left on disk','HTTP 403 forbidden'])
def test_permanent_errors_never_retry(message):
    assert retry_delay(dict(status='error',error=message)) is None


def test_transient_backoff_exhaustion_and_user_stop():
    job=dict(status='error',error='HTTP Error 503: service unavailable')
    assert [retry_delay(dict(job,retry_count=n)) for n in range(4)]==[5,15,45,None]
    assert retry_delay(dict(job,status='paused')) is None
    assert retry_delay(dict(job,user_stopped=True)) is None
    assert retry_delay(dict(job,error='Unknown error')) is None


def test_schedule_holds_new_jobs_and_crosses_midnight():
    assert not schedule_allows(datetime(2026,10,15,8),start_at='2026-10-15T09:00')
    assert schedule_allows(datetime(2026,10,15,9),start_at='2026-10-15T09:00')
    for hour in (23,0,5):assert not schedule_allows(datetime(2026,10,15,hour),quiet_start='22:00',quiet_end='06:00')
    assert schedule_allows(datetime(2026,10,15,6),quiet_start='22:00',quiet_end='06:00')
    assert not schedule_allows(datetime.now(),quiet_start='invalid',quiet_end='06:00')
    assert not schedule_allows(datetime.now(),start_at='invalid')


def test_disk_headroom_and_unknown_size(tmp_path):
    job=dict(estimated_bytes=100*1024*1024,config=dict(outdir=str(tmp_path/'missing'/'folder')))
    required=disk_space_required(job)
    assert required>200*1024*1024
    assert check_disk_space(job,required-1)==(False,required,required-1)
    assert check_disk_space(job,required)[0]
    assert disk_space_required(dict(job,downloaded=50*1024*1024))<required
    assert disk_space_required(dict(job,kind='conversion'))>required
    assert disk_space_required({})==64*1024*1024
    assert disk_space_required(dict(estimated_bytes=float('inf')))==64*1024*1024
