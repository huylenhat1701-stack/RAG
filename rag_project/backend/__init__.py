import sys
if sys.platform == "win32":
    import platform
    from collections import namedtuple
    _uname_result = namedtuple('uname_result', ['system', 'node', 'release', 'version', 'machine'])
    platform.uname = lambda: _uname_result(system='Windows', node='UNKNOWN', release='10', version='10.0.22631', machine='AMD64')
