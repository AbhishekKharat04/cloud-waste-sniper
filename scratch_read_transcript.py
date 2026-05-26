import json

path = r"C:\Users\rkhar\.gemini\antigravity\brain\b0a0f125-67b6-42a8-9723-6c819b9d22c1\.system_generated\logs\transcript.jsonl"
with open(path, "r", encoding="utf-8") as f:
    for line in f:
        data = json.loads(line)
        step = data.get("step_index")
        if step == 203:
            tool_calls = data.get("tool_calls", [])
            for call in tool_calls:
                args = call.get("args", {})
                content = args.get("CodeContent")
                with open("src/scraper_step203.py", "w", encoding="utf-8") as out:
                    out.write(content)
                print("Wrote scraper_step203.py successfully!")
        elif step == 228:
            tool_calls = data.get("tool_calls", [])
            for call in tool_calls:
                args = call.get("args", {})
                content = args.get("ReplacementContent")
                with open("src/scraper_step228.py", "w", encoding="utf-8") as out:
                    out.write(content)
                print("Wrote scraper_step228.py successfully!")
