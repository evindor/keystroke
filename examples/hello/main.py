import json
import sys

request = json.loads(sys.stdin.readline())
name = request["query"][5:].strip() or "Omarchy"
value = request["settings"].get("greeting", "Hello") + ", " + name + "!"
print(json.dumps({"rows": [{"id": "hello", "title": value, "subtitle": "Copy this greeting",
    "icon": "✳", "score": 100, "action": {"type": "copy", "text": value}}]}))
