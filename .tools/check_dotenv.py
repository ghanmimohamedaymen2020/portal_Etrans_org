import sys, importlib

try:
    m = importlib.import_module('dotenv')
    print('dotenv module file:', getattr(m, '__file__', None))
    print('module repr:', repr(m))
    print('possible attrs:', [a for a in dir(m) if 'load' in a.lower() or 'dotenv' in a.lower()][:50])
except Exception as e:
    print('IMPORT ERROR:', type(e).__name__, e)
    try:
        import pkg_resources
        pkgs = [p for p in pkg_resources.working_set if 'dotenv' in p.key or 'python-dotenv' in p.key]
        print('related installed packages:')
        for p in pkgs:
            print('-', p.key, p.version)
    except Exception:
        print('Could not list installed packages via pkg_resources')
    sys.exit(1)

print('\nModule OK. Trying to import load_dotenv attribute...')
try:
    from dotenv import load_dotenv
    print('load_dotenv is available')
except Exception as e:
    print('load_dotenv import failed:', type(e).__name__, e)
    # Show object members
    try:
        import dotenv as m
        print('members on module:', [x for x in dir(m)][:200])
    except Exception as e2:
        print('Also failed to inspect module:', type(e2).__name__, e2)
    sys.exit(1)

print('All checks passed')
