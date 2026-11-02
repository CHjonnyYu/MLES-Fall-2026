"""Install the public-static path guard without replacing an existing course backend.

Run once while building a runtime image:
    python server/static_path_guard.py /app/server/app.py
The patch is idempotent and retains every other backend function and route.
"""
from pathlib import Path
import ast
import hashlib
import sys

MARKER = '# Reject traversal before applying public path prefixes.'
GUARD = """        # Reject traversal before applying public path prefixes.
        if chr(92) in filename or any(part in {'.', '..'} for part in filename.split('/')):
            abort(404)
"""


def install(path):
    path = Path(path)
    source = path.read_text(encoding='utf-8')
    if MARKER in source:
        return False
    needle = '    def public_static(filename):\n'
    if source.count(needle) != 1:
        raise RuntimeError('Expected one public_static handler; no patch applied.')
    changed = source.replace(needle, needle + GUARD, 1)
    ast.parse(changed)
    path.write_text(changed, encoding='utf-8')
    print('Static path guard installed; backend SHA256', hashlib.sha256(changed.encode()).hexdigest())
    return True


if __name__ == '__main__':
    if len(sys.argv) != 2:
        raise SystemExit('Usage: static_path_guard.py PATH_TO_APP')
    install(sys.argv[1])
