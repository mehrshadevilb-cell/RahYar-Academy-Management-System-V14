import json
from pathlib import Path


class AgentMemory:
    def __init__(self, path='.ai-agent/memory.json'):
        self.path = Path(path)

    def read(self):
        if not self.path.exists():
            return {}
        return json.loads(self.path.read_text(encoding='utf-8'))

    def write(self, data):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(
            json.dumps(data, indent=2, ensure_ascii=False),
            encoding='utf-8'
        )
