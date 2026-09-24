import os
import json
from tools_def import TOOLS

def export():
    targets = [
        r"C:\Users\johna\.gemini\antigravity\mcp\cluster-work",
        r"C:\Users\johna\.gemini\antigravity-cli\mcp\cluster-work"
    ]
    for target in targets:
        os.makedirs(target, exist_ok=True)
        for t in TOOLS:
            schema = {
                "name": t["name"],
                "description": t["description"],
                "parameters": t["inputSchema"]
            }
            path = os.path.join(target, f"{t['name']}.json")
            with open(path, "w", encoding="utf-8") as f:
                json.dump(schema, f, indent=2)
        print(f"Exported {len(TOOLS)} tool schemas to {target}")

if __name__ == "__main__":
    export()
