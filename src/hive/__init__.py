__version__ = '0.1.0'
__all__ = ['Anon', 'Bad', 'Cfg', 'Clash', 'Denied', 'Err', 'Hive', 'Missing', 'Sess', '__version__', 'load']
_AT = {'Cfg': 'cfg', 'load': 'cfg', 'Hive': 'core', 'Sess': 'sess', **dict.fromkeys(('Anon', 'Bad', 'Clash', 'Denied', 'Err', 'Missing'), 'err')}


def __getattr__(n):
    if n not in _AT: raise AttributeError(f'module hive has no attribute {n!r}')
    from importlib import import_module
    return getattr(import_module(f'.{_AT[n]}', __name__), n)
