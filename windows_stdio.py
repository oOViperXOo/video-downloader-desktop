"""Restore inherited worker pipes in a Windows GUI executable, without a console."""
import sys


def restore_worker_streams():
    if sys.platform != 'win32':
        return
    import ctypes
    import io
    import msvcrt
    import os
    get_handle = ctypes.windll.kernel32.GetStdHandle
    get_handle.argtypes = [ctypes.c_ulong]
    get_handle.restype = ctypes.c_void_p
    for name, handle_id in (('stdout', 0xFFFFFFF5), ('stderr', 0xFFFFFFF4)):
        if getattr(sys, name) is not None:
            continue
        handle = get_handle(handle_id)
        if handle and handle != ctypes.c_void_p(-1).value:
            fd = msvcrt.open_osfhandle(handle, os.O_WRONLY | os.O_BINARY)
            stream = io.TextIOWrapper(os.fdopen(fd, 'wb', buffering=0), encoding='utf-8',
                                      errors='replace', write_through=True)
        else:
            stream = open(os.devnull, 'w', encoding='utf-8')
        setattr(sys, name, stream)
        setattr(sys, '__' + name + '__', stream)
