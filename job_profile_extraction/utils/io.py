import json
from pathlib import Path
import pandas as pd


def load_json(path):
    p = Path(path)
    if not p.exists():
        return []
    with open(p, encoding='utf-8') as f:
        return json.load(f)


def save_csv(rows, path):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    flat_rows = [
        {k: ('; '.join(v) if isinstance(v, list) else v) for k, v in row.items()}
        for row in rows
    ]
    pd.DataFrame(flat_rows).to_csv(path, index=False, encoding='utf-8-sig')


def save_json(rows, path):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(rows, f, ensure_ascii=False, indent=2)
