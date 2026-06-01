import json
from pathlib import Path

p = Path(__file__).parent.parent / "data" / "lolz_market_openapi.json"
if not p.exists():
  p = Path(r"C:\Users\Дима\.cursor\projects\c-Users-Desktop-tg-sender\agent-tools\aae953d8-394c-4695-9f06-543ca225e025.txt")
d = json.loads(p.read_text(encoding="utf-8"))
for path, methods in sorted(d["paths"].items()):
    for m, spec in methods.items():
        if m in ("get", "post", "put", "delete", "patch"):
            print(f"{m.upper():6} {path:50} {spec.get('summary', '')[:60]}")
