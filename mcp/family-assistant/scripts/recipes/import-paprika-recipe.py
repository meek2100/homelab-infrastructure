#!/usr/bin/env python3
"""
Paprika Recipe Importer (URL & Text to Paprika Cloud & Obsidian)
Parses recipes from web URLs, blog posts, or raw text, uploads directly to Paprika Cloud Sync,
and archives the markdown note to the Obsidian Second Brain vault.
"""

import os
import sys
import json
import argparse
import datetime
import uuid
import re
import urllib.request
import requests
from bs4 import BeautifulSoup

DEFAULT_VAULT_DIR = os.environ.get(
    "OBSIDIAN_VAULT_PATH",
    "/mnt/c/Users/dtheurer/Obsidian/Vault/Personal"
)
CONFIG_DIR = os.path.expanduser("~/.config/homelab-todo")
CREDENTIALS_FILE = os.path.join(CONFIG_DIR, "paprika.json")
CACHE_FILE = os.path.join(CONFIG_DIR, "paprika_cache.json")
BASE_URL = "https://www.paprikaapp.com/api/v1/sync"
OLLAMA_ENDPOINT = os.environ.get("OLLAMA_API_URL", "http://192.168.40.246:11434")


def load_credentials():
    if not os.path.exists(CREDENTIALS_FILE):
        print(f"❌ Credentials file not found: {CREDENTIALS_FILE}")
        sys.exit(1)
    with open(CREDENTIALS_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)
        return data.get("email"), data.get("password")


def slugify(text):
    text = text.lower().strip()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[\s_-]+", "-", text)
    return text.strip("-")


def parse_iso_duration(iso_str):
    if not iso_str or not isinstance(iso_str, str):
        return ""
    m = re.match(r"PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", iso_str)
    if m:
        hours, mins, _ = m.groups()
        parts = []
        if hours:
            parts.append(f"{hours} hr" + ("s" if int(hours) > 1 else ""))
        if mins:
            parts.append(f"{mins} min" + ("s" if int(mins) > 1 else ""))
        if parts:
            return " ".join(parts)
    return iso_str


def parse_instructions(raw_inst):
    steps = []
    if isinstance(raw_inst, list):
        for item in raw_inst:
            if isinstance(item, dict):
                text = item.get("text") or item.get("name") or ""
                if text.strip():
                    steps.append(text.strip())
            elif isinstance(item, str) and item.strip():
                steps.append(item.strip())
    elif isinstance(raw_inst, str):
        for line in raw_inst.splitlines():
            line_str = line.strip()
            if line_str:
                clean = re.sub(r"^\d+[\.\)]\s*", "", line_str)
                steps.append(clean)
    return steps


def extract_recipe_from_json_ld(soup):
    for script in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(script.string)
            items = []
            if isinstance(data, list):
                items = data
            elif isinstance(data, dict):
                if "@graph" in data and isinstance(data["@graph"], list):
                    items = data["@graph"]
                else:
                    items = [data]

            for it in items:
                t = it.get("@type")
                if t == "Recipe" or (isinstance(t, list) and "Recipe" in t):
                    name = it.get("name", "").strip()
                    desc = it.get("description", "").strip()
                    ingredients = it.get("recipeIngredient", [])
                    instructions = parse_instructions(it.get("recipeInstructions", []))
                    prep_time = parse_iso_duration(it.get("prepTime", ""))
                    cook_time = parse_iso_duration(it.get("cookTime", ""))
                    total_time = parse_iso_duration(it.get("totalTime", ""))
                    yield_val = it.get("recipeYield")
                    servings = str(yield_val[0] if isinstance(yield_val, list) else yield_val or "")

                    # Extract image
                    img_data = it.get("image")
                    photo_url = ""
                    if isinstance(img_data, str):
                        photo_url = img_data
                    elif isinstance(img_data, list) and img_data:
                        photo_url = img_data[0] if isinstance(img_data[0], str) else img_data[0].get("url", "")
                    elif isinstance(img_data, dict):
                        photo_url = img_data.get("url", "")

                    if name and ingredients and instructions:
                        return {
                            "name": name,
                            "description": desc,
                            "ingredients": ingredients,
                            "directions": instructions,
                            "prep_time": prep_time,
                            "cook_time": cook_time,
                            "total_time": total_time,
                            "servings": servings,
                            "photo_url": photo_url
                        }
        except Exception:
            continue
    return None


def extract_recipe_via_llm(raw_text, url=""):
    print("🧠 Extracting structured recipe via local Ollama LLM on CT 104...")
    prompt = f"""You are a professional culinary assistant. Extract the recipe from the provided text into a clean JSON object.
Text to parse:
---
{raw_text[:6000]}
---

Return strictly valid JSON with no markdown backticks, matching this exact schema:
{{
  "name": "Recipe Title",
  "description": "Short 1-2 sentence description",
  "prep_time": "15 mins",
  "cook_time": "30 mins",
  "total_time": "45 mins",
  "servings": "4",
  "ingredients": ["1 cup flour", "2 eggs", "..."],
  "directions": ["Step 1 directions", "Step 2 directions", "..."],
  "photo_url": ""
}}"""
    try:
        req = urllib.request.Request(
            f"{OLLAMA_ENDPOINT}/api/generate",
            data=json.dumps({
                "model": "qwen2.5:3b-instruct",
                "prompt": prompt,
                "stream": False,
                "format": "json"
            }).encode("utf-8"),
            headers={"Content-Type": "application/json"}
        )
        with urllib.request.urlopen(req, timeout=60) as res:
            res_data = json.loads(res.read().decode("utf-8"))
            parsed = json.loads(res_data.get("response", "{}"))
            return parsed
    except Exception as e:
        print(f"⚠️ LLM extraction error: {e}")
        return None


def fetch_url(url):
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"
    }
    res = requests.get(url, headers=headers, timeout=20)
    res.raise_for_status()
    return res.text


def get_category_uid(session, category_name):
    if not category_name:
        return None
    try:
        res = session.get(f"{BASE_URL}/categories/", timeout=15)
        if res.status_code == 200:
            cats = res.json().get("result", [])
            q = category_name.lower().strip()
            for c in cats:
                if c.get("name", "").lower() == q:
                    return c.get("uid")
                if q in c.get("name", "").lower():
                    return c.get("uid")
            # If category doesn't exist, create it in Paprika
            new_cat_uid = str(uuid.uuid4()).upper()
            create_res = session.post(
                f"{BASE_URL}/categories/",
                data={"data": json.dumps({"uid": new_cat_uid, "name": category_name})}
            )
            if create_res.status_code == 200:
                print(f"  + Created new Paprika category: '{category_name}'")
                return new_cat_uid
    except Exception as e:
        print(f"Warning matching category: {e}")
    return None


def upload_recipe_to_paprika(session, recipe_dict, category_name=None, source_url=""):
    uid = str(uuid.uuid4()).upper()
    cat_uid = get_category_uid(session, category_name)
    categories = [cat_uid] if cat_uid else []

    ing_list = recipe_dict.get("ingredients", [])
    ingredients_str = "\n".join(ing_list) if isinstance(ing_list, list) else str(ing_list)

    dir_list = recipe_dict.get("directions", [])
    directions_str = "\n".join(dir_list) if isinstance(dir_list, list) else str(dir_list)

    import gzip
    import hashlib

    hash_val = hashlib.sha256(uid.encode("utf-8")).hexdigest().upper()
    payload = {
        "uid": uid,
        "name": recipe_dict.get("name", "Imported Recipe"),
        "description": recipe_dict.get("description", ""),
        "notes": "",
        "nutritional_info": "",
        "ingredients": ingredients_str,
        "directions": directions_str,
        "prep_time": recipe_dict.get("prep_time", ""),
        "prep_minutes": None,
        "cook_time": recipe_dict.get("cook_time", ""),
        "cook_minutes": None,
        "total_time": recipe_dict.get("total_time", ""),
        "total_minutes": None,
        "servings": str(recipe_dict.get("servings", "")),
        "servings_min": None,
        "servings_max": None,
        "difficulty": "",
        "source": "Homelab Assistant",
        "source_url": source_url,
        "image_url": None,
        "photo": None,
        "photo_hash": None,
        "photo_large": None,
        "photo_url": None,
        "scale": None,
        "hash": hash_val,
        "created": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "categories": categories,
        "in_trash": False,
        "is_pinned": False,
        "on_favorites": False,
        "on_grocery_list": False,
        "rating": 0,
        "cookbook_uid": None,
        "metadata_version": None,
        "nutrition": None
    }

    url = f"{BASE_URL}/recipe/{uid}/"
    json_bytes = json.dumps(payload).encode("utf-8")
    gzipped_data = gzip.compress(json_bytes)
    files = {"data": ("data", gzipped_data, "application/octet-stream")}

    res = session.post(url, files=files, timeout=15)
    if res.status_code == 200:
        print(f"✅ Successfully uploaded '{payload['name']}' to Paprika Cloud Sync!")
        return uid, payload
    else:
        print(f"❌ Failed to upload to Paprika: HTTP {res.status_code} - {res.text}")
        return None, None


def save_recipe_to_vault(vault_dir, recipe_payload, category_name=None):
    recipes_dir = os.path.join(vault_dir, "Recipes")
    os.makedirs(recipes_dir, exist_ok=True)

    name = recipe_payload.get("name", "Untitled Recipe")
    slug = slugify(name)
    filename = f"{slug}.md"
    filepath = os.path.join(recipes_dir, filename)

    prep = recipe_payload.get("prep_time", "")
    cook = recipe_payload.get("cook_time", "")
    servings = recipe_payload.get("servings", "")
    source_url = recipe_payload.get("source_url", "")

    lines = ["---"]
    lines.append("type: recipe")
    lines.append(f'title: "{name}"')
    if servings:
        lines.append(f'servings: "{servings}"')
    if prep:
        lines.append(f'prep_time: "{prep}"')
    if cook:
        lines.append(f'cook_time: "{cook}"')
    if source_url:
        lines.append(f'source_url: "{source_url}"')
    lines.append("tags:")
    lines.append("  - recipe")
    lines.append("  - paprika")
    if category_name:
        lines.append(f"  - recipe/{slugify(category_name)}")
        lines.append(f'categories:\n  - "{category_name}"')
    lines.append("---\n")

    lines.append(f"# 🍲 {name}\n")
    meta = []
    if prep:
        meta.append(f"**Prep**: {prep}")
    if cook:
        meta.append(f"**Cook**: {cook}")
    if servings:
        meta.append(f"**Servings**: {servings}")
    if category_name:
        meta.append(f"**Category**: {category_name}")
    if meta:
        lines.append(f"* {' | '.join(meta)} *\n")

    desc = recipe_payload.get("description", "").strip()
    if desc:
        lines.append(f"{desc}\n")

    lines.append("## 🛒 Ingredients\n")
    for ing in recipe_payload.get("ingredients", "").splitlines():
        if ing.strip():
            lines.append(f"- {ing.strip()}")
    lines.append("")

    lines.append("## 👩‍🍳 Directions\n")
    step = 1
    for d in recipe_payload.get("directions", "").splitlines():
        if d.strip():
            lines.append(f"{step}. {d.strip()}")
            step += 1
    lines.append("")

    with open(filepath, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print(f"✅ Saved markdown note to {filepath}")


def import_recipe(url=None, text=None, category=None, vault_dir=DEFAULT_VAULT_DIR):
    recipe_data = None
    source_url = url or ""

    if url:
        print(f"🌐 Fetching recipe from URL: {url}...")
        try:
            html = fetch_url(url)
            soup = BeautifulSoup(html, "html.parser")
            recipe_data = extract_recipe_from_json_ld(soup)
            if not recipe_data:
                print("ℹ️ No Schema.org JSON-LD found; extracting via LLM...")
                body_text = soup.get_text(separator="\n", strip=True)
                recipe_data = extract_recipe_via_llm(body_text, url)
        except Exception as e:
            print(f"❌ Failed to fetch URL: {e}")
            sys.exit(1)

    elif text:
        recipe_data = extract_recipe_via_llm(text)

    if not recipe_data or not recipe_data.get("name"):
        print("❌ Could not extract recipe details.")
        sys.exit(1)

    print(f"\n📋 Extracted Recipe: '{recipe_data.get('name')}'")
    print(f"  • Ingredients: {len(recipe_data.get('ingredients', []))} items")
    print(f"  • Directions:  {len(recipe_data.get('directions', []))} steps")

    email, password = load_credentials()
    session = requests.Session()
    session.auth = (email, password)

    uid, payload = upload_recipe_to_paprika(session, recipe_data, category_name=category, source_url=source_url)
    if payload:
        save_recipe_to_vault(vault_dir, payload, category_name=category)
        return payload
    return None


def main():
    parser = argparse.ArgumentParser(description="Import recipes from URLs or text into Paprika and Obsidian.")
    parser.add_argument("--url", "-u", help="URL of recipe to scrape and import.")
    parser.add_argument("--text", "-t", help="Raw recipe text to parse.")
    parser.add_argument("--category", "-c", help="Paprika category (e.g. 'Oven Baked Dinner', 'Cookies').")
    parser.add_argument("--vault-dir", default=DEFAULT_VAULT_DIR, help="Obsidian vault directory.")
    args = parser.parse_args()

    if not args.url and not args.text:
        parser.print_help()
        sys.exit(1)

    import_recipe(url=args.url, text=args.text, category=args.category, vault_dir=args.vault_dir)


if __name__ == "__main__":
    main()
