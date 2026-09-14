from pathlib import Path


class ProjectScanner:
    def __init__(self, root='.'):
        self.root = Path(root)

    def scan(self):
        return {
            'python_files': len(list(self.root.rglob('*.py'))),
            'has_tests': (self.root / 'tests').exists(),
            'has_alembic': (self.root / 'alembic').exists(),
            'has_docker': (self.root / 'Dockerfile').exists(),
        }
