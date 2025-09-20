import json
from pathlib import Path

FILE = Path("connected_groups.json")

def load_groups():
    if FILE.exists():
        with open(FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def save_groups(data):
    with open(FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
def add_group(user_id: int, group_id: int):
    data = load_groups()
    data[str(user_id)] = group_id
    save_groups(data)