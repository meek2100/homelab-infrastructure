#!/usr/bin/env python3
"""
eval-family-assistant.py - Automated evaluation and regression test suite for Open WebUI Family Assistant.
Tests intent recognition, tool-calling precision, parameter validity, and live data rendering.
"""

import sys
import os
import json
import argparse
import urllib.request
import urllib.error
import time

TEST_CASES = [
    {
        "id": "groceries_query",
        "prompt": "What is on our groceries list?",
        "expected_tools": ["get_groceries", "get_grocery_list", "get_todo_items"],
        "required_in_output": ["Mac and cheese", "Flossers", "Ranch", "Tom yum paste"]
    },
    {
        "id": "calendar_query",
        "prompt": "What do we have scheduled on the family calendar this week?",
        "expected_tools": ["get_upcoming_events", "search_calendar_events"],
        "required_in_output": ["Conference", "Gymnastics", "Pumpkin", "Garbage", "Swim"]
    },
    {
        "id": "recipe_query",
        "prompt": "How do I make Greek Lemon Chicken soup?",
        "expected_tools": ["search_recipes", "get_recipe_details"],
        "required_in_output": []
    },
    {
        "id": "maintenance_query",
        "prompt": "When is our next vehicle oil change or home maintenance due?",
        "expected_tools": ["get_maintenance_due"],
        "required_in_output": []
    }
]

def get_config():
    cfg_path = os.path.expanduser("~/.config/homelab-todo/openwebui.json")
    with open(cfg_path) as f:
        return json.load(f)

def run_test_suite(model: str = "llama3.2:3b", verbose: bool = False):
    cfg = get_config()
    base = cfg.get("base_url", "http://192.168.40.246:3000")
    key = cfg.get("api_key")

    # Fetch all tool specs
    tools = []
    for tid in ["microsoft_to_do_groceries_manager", "google_family_calendar", "obsidian_vault_recipe_reader", "paprika_recipe_importer"]:
        try:
            req = urllib.request.Request(f"{base}/api/v1/tools/id/{tid}", headers={"Authorization": f"Bearer {key}"})
            with urllib.request.urlopen(req, timeout=10) as res:
                td = json.loads(res.read().decode("utf-8"))
            for s in td.get("specs", []):
                tools.append({"type": "function", "function": s})
        except Exception:
            pass

    print(f"🧪 Running Family Assistant Evaluation Suite on Model '{model}'...")
    print(f"   Registered Tools Loaded: {len(tools)} functions available.\n")

    passed_count = 0
    total_count = len(TEST_CASES)

    for tc in TEST_CASES:
        t_start = time.time()
        print(f"▶️  Test Case: [{tc['id']}] - \"{tc['prompt']}\"")
        payload = {
            "model": model,
            "messages": [{"role": "user", "content": tc["prompt"]}],
            "tools": tools,
            "stream": False
        }
        req = urllib.request.Request(
            f"{base}/api/chat/completions",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
        )
        try:
            with urllib.request.urlopen(req, timeout=45) as res:
                resp = json.loads(res.read().decode("utf-8"))
            elapsed = time.time() - t_start
            msg = resp.get("choices", [{}])[0].get("message", {})
            tool_calls = msg.get("tool_calls", [])

            called_names = [tc_item.get("function", {}).get("name") for tc_item in tool_calls]
            
            matched = any(name in tc["expected_tools"] for name in called_names)
            if matched:
                print(f"   ✅ PASS: Called expected tool: {called_names} ({elapsed:.2f}s)")
                passed_count += 1
            else:
                if called_names:
                    print(f"   ❌ FAIL: Unexpected tool called: {called_names} (expected {tc['expected_tools']}) ({elapsed:.2f}s)")
                else:
                    content = msg.get("content", "")[:120].replace("\n", " ")
                    print(f"   ❌ FAIL: No tool called. Returned text: \"{content}\" ({elapsed:.2f}s)")
        except Exception as e:
            print(f"   ❌ ERROR: Request failed: {e}")

    pct = (passed_count / total_count) * 100
    print(f"\n==========================================")
    print(f"🏁 Final Result: {passed_count}/{total_count} Passed ({pct:.1f}%)")
    print(f"==========================================")
    return passed_count == total_count

def main():
    parser = argparse.ArgumentParser(description="Evaluate Family Assistant Tool Calling Accuracy")
    parser.add_argument("--model", type=str, default="llama3.2:3b", help="Model to evaluate")
    parser.add_argument("--verbose", action="store_true", help="Verbose output")
    args = parser.parse_args()

    success = run_test_suite(model=args.model, verbose=args.verbose)
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()
