"""Keep Qt on Windows' ICU, rather than an unrelated same-name DLL on PATH."""
import os
import sys

if sys.platform == 'win32':
    import ctypes
    # Qt's Windows wheel imports the unversioned ICU API supplied by Windows.
    # Other tools (e.g. Poppler) ship an incompatible icuuc.dll with versioned APIs.
    _windows_icu = ctypes.WinDLL('icuuc.dll', winmode=0x00000800)  # LOAD_LIBRARY_SEARCH_SYSTEM32
