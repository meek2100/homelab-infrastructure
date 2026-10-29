#!/usr/bin/env python3
"""
manage-ollama.py - Manage, benchmark, and profile Ollama models on CT 104.
"""

import sys
import os
import json
import argparse
import urllib.request
import urllib.error
import time

raw_host = os.environ.get("HOMELAB_OLLAMA_HOST") or "http://192.168.40.246:11434"
if not raw_host.startswith("http://") and not raw_host.startswith("https://"):
    OLLAMA_HOST = f"http://{raw_host}"
else:
    OLLAMA_HOST = raw_host

def list_models():
    url = f"{OLLAMA_HOST}/api/tags"
    try:
        with urllib.request.urlopen(url, timeout=10) as res:
            data = json.loads(res.read().decode("utf-8"))
        models = data.get("models", [])
        print(f"📦 Registered Models on {OLLAMA_HOST} ({len(models)} total):")
        for m in models:
            size_mb = m.get("size", 0) / (1024 * 1024)
            print(f"  • {m.get('name'):<25} | Size: {size_mb:8.1f} MB | Modified: {m.get('modified_at', '')[:19]}")
    except Exception as e:
        print(f"Error fetching models: {e}", file=sys.stderr)
        sys.exit(1)

def vram_profile():
    url = f"{OLLAMA_HOST}/api/ps"
    try:
        with urllib.request.urlopen(url, timeout=10) as res:
            data = json.loads(res.read().decode("utf-8"))
        active = data.get("models", [])
        if not active:
            print(f"💤 No models currently loaded in memory on {OLLAMA_HOST}.")
            return
        print(f"⚡ Currently Loaded Models in Memory / VRAM ({len(active)} active):")
        for m in active:
            total_b = m.get("size", 1)
            vram_b = m.get("size_vram", 0)
            pct = (vram_b / total_b) * 100 if total_b else 0
            size_mb = total_b / (1024 * 1024)
            vram_mb = vram_b / (1024 * 1024)
            print(f"  • {m.get('name'):<25}")
            print(f"    - Parameter Size : {m.get('details', {}).get('parameter_size', 'unknown')}")
            print(f"    - Quantization   : {m.get('details', {}).get('quantization_level', 'unknown')}")
            print(f"    - VRAM Allocation: {vram_mb:6.1f} MB / {size_mb:6.1f} MB ({pct:5.1f}% in GPU)")
            print(f"    - Context Length : {m.get('context_length', 4096)} tokens")
            print(f"    - Runner Engine  : {m.get('runner', 'unknown')}")
            print(f"    - Expires In     : {m.get('expires_at', '')[:19]}")
    except Exception as e:
        print(f"Error profiling VRAM: {e}", file=sys.stderr)
        sys.exit(1)

def pull_model(model_name: str):
    url = f"{OLLAMA_HOST}/api/pull"
    payload = json.dumps({"name": model_name, "stream": False}).encode("utf-8")
    print(f"📥 Pulling model '{model_name}' on {OLLAMA_HOST} (this may take a couple of minutes)...")
    try:
        req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=600) as res:
            out = json.loads(res.read().decode("utf-8"))
            print(f"✅ Pull status: {out.get('status', 'success')}")
    except Exception as e:
        print(f"Error pulling model: {e}", file=sys.stderr)
        sys.exit(1)

def delete_model(model_name: str):
    url = f"{OLLAMA_HOST}/api/delete"
    payload = json.dumps({"name": model_name}).encode("utf-8")
    try:
        req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"}, method="DELETE")
        with urllib.request.urlopen(req, timeout=15) as res:
            print(f"🗑️ Successfully deleted model '{model_name}'.")
    except Exception as e:
        print(f"Error deleting model: {e}", file=sys.stderr)
        sys.exit(1)

def benchmark(model_name: str, num_predict: int = 40):
    url = f"{OLLAMA_HOST}/api/generate"
    print(f"⏱️ Running benchmark for '{model_name}' on {OLLAMA_HOST}...")

    # Benchmark 1: Short prompt (Raw generation speed)
    short_payload = json.dumps({
        "model": model_name,
        "prompt": "Count from 1 to 30 sequentially:",
        "stream": False,
        "options": {"num_predict": num_predict}
    }).encode("utf-8")

    try:
        req = urllib.request.Request(url, data=short_payload, headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=60) as res:
            out = json.loads(res.read().decode("utf-8"))
        
        eval_count = out.get("eval_count", 0)
        eval_duration = out.get("eval_duration", 1) / 1e9
        p_count = out.get("prompt_eval_count", 0)
        p_duration = out.get("prompt_eval_duration", 1) / 1e9

        gen_rate = eval_count / eval_duration if eval_duration else 0
        prompt_rate = p_count / p_duration if p_duration else 0

        print(f"📊 Results for {model_name}:")
        print(f"  • Prompt Evaluation : {prompt_rate:6.1f} tokens/sec ({p_count} tokens in {p_duration:.2f}s)")
        print(f"  • Token Generation  : {gen_rate:6.1f} tokens/sec ({eval_count} tokens in {eval_duration:.2f}s)")
        print(f"  • Total Duration    : {(out.get('total_duration', 0) / 1e9):.2f}s")
        print(f"  • Sample Output     : {repr(out.get('response', '')[:60])}...")
    except Exception as e:
        print(f"Error benchmarking model: {e}", file=sys.stderr)
        sys.exit(1)

def main():
    parser = argparse.ArgumentParser(description="Manage and profile Ollama models on homelab CT 104")
    parser.add_argument("action", choices=["list", "vram", "pull", "delete", "benchmark"])
    parser.add_argument("--model", type=str, help="Model name (e.g. llama3.2:3b, hermes3:3b, qwen2.5:1.5b-instruct)")
    parser.add_argument("--tokens", type=int, default=40, help="Number of tokens to generate during benchmark")
    args = parser.parse_args()

    if args.action == "list":
        list_models()
    elif args.action == "vram":
        vram_profile()
    elif args.action == "pull":
        if not args.model:
            print("Error: --model required for pull", file=sys.stderr)
            sys.exit(1)
        pull_model(args.model)
    elif args.action == "delete":
        if not args.model:
            print("Error: --model required for delete", file=sys.stderr)
            sys.exit(1)
        delete_model(args.model)
    elif args.action == "benchmark":
        if not args.model:
            print("Error: --model required for benchmark", file=sys.stderr)
            sys.exit(1)
        benchmark(args.model, args.tokens)

if __name__ == "__main__":
    main()
