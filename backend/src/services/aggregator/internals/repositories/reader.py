import json
from typing import List, Optional


class JsonlReader:
    def read(self, file_path: str, limit: Optional[int] = None) -> List[dict]:
        records = []
        with open(file_path, "r", encoding="utf-8") as f:
            for i, line in enumerate(f):
                if limit and i >= limit:
                    break
                try:
                    records.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
        return records
