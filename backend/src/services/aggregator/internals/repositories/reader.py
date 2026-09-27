import json
from typing import Any, Dict, List, Optional


class JsonlReader:
    def read(self, file_path: str, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        records: List[Dict[str, Any]] = []
        with open(file_path, "r", encoding="utf-8") as f:
            for i, line in enumerate(f):
                if limit and i >= limit:
                    break
                stripped = line.strip()
                if not stripped:
                    continue
                try:
                    records.append(json.loads(stripped))
                except json.JSONDecodeError:
                    continue
        return records
