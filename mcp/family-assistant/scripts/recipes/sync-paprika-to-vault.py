#!/usr/bin/env python3
"""
Paprika Recipe Manager to Obsidian Vault Sync Engine
Synchronizes recipes, meal plans, and grocery items from Paprika Cloud Sync into static Markdown in the local Obsidian vault.
Integrates with the daily morning briefing engine for meal planning and dinner recommendations.
"""

import os
import sys
import json
import argparse
import datetime
import re
import requests

DEFAULT_VAULT_DIR = os.environ.get(
    "OBSIDIAN_VAULT_PATH",
    "/mnt/c/Users/dtheurer/Obsidian/Vault/Personal"
)
CONFIG_DIR = os.path.expanduser("~/.config/homelab-todo")
CREDENTIALS_FILE = os.path.join(CONFIG_DIR, "paprika.json")
CACHE_FILE = os.path.join(CONFIG_DIR, "paprika_cache.json")
BASE_URL = "https://www.paprikaapp.com/api/v1/sync"


def load_credentials():
    if not os.path.exists(CREDENTIALS_FILE):
        print(f"❌ Credentials file not found: {CREDENTIALS_FILE}")
        print("Please create ~/.config/homelab-todo/paprika.json with {\"email\": \"...\", \"password\": \"...\"}")
        sys.exit(1)
    try:
        with open(CREDENTIALS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            email = data.get("email")
            password = data.get("password")
            if not email or not password:
                print("❌ 'email' or 'password' missing in paprika.json")
                sys.exit(1)
            return email, password
    except Exception as e:
        print(f"❌ Error reading {CREDENTIALS_FILE}: {e}")
        sys.exit(1)


def load_cache():
    if os.path.exists(CACHE_FILE):
        try:
            with open(CACHE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {"recipe_hashes": {}}


def save_cache(cache):
    try:
        os.makedirs(CONFIG_DIR, mode=0o700, exist_ok=True)
        with open(CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(cache, f, indent=2)
        os.chmod(CACHE_FILE, 0o600)
    except Exception as e:
        print(f"Warning saving cache: {e}")


def slugify(text):
    text = text.lower().strip()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[\s_-]+", "-", text)
    return text.strip("-")


def get_categories(session):
    try:
        res = session.get(f"{BASE_URL}/categories/", timeout=15)
        if res.status_code == 200:
            cats = res.json().get("result", [])
            return {c["uid"]: c["name"] for c in cats if "uid" in c and "name" in c}
    except Exception as e:
        print(f"Warning fetching categories: {e}")
    return {}


def render_recipe_markdown(recipe, category_map):
    name = recipe.get("name", "Untitled Recipe").strip()
    servings = recipe.get("servings") or ""
    prep_time = recipe.get("prep_time") or ""
    cook_time = recipe.get("cook_time") or ""
    total_time = recipe.get("total_time") or ""
    difficulty = recipe.get("difficulty") or ""
    source = recipe.get("source") or ""
    source_url = recipe.get("source_url") or ""
    rating = recipe.get("rating", 0)

    # Categories
    cat_uids = recipe.get("categories") or []
    cat_names = [category_map.get(uid, uid) for uid in cat_uids if uid in category_map]

    ingredients_raw = recipe.get("ingredients") or ""
    directions_raw = recipe.get("directions") or ""
    notes_raw = recipe.get("notes") or ""
    description_raw = recipe.get("description") or ""

    md = ["---"]
    md.append("type: recipe")
    md.append(f'title: "{name}"')
    if servings:
        md.append(f'servings: "{servings}"')
    if prep_time:
        md.append(f'prep_time: "{prep_time}"')
    if cook_time:
        md.append(f'cook_time: "{cook_time}"')
    if total_time:
        md.append(f'total_time: "{total_time}"')
    if difficulty:
        md.append(f'difficulty: "{difficulty}"')
    if rating:
        md.append(f"rating: {rating}")
    if source:
        md.append(f'source: "{source}"')
    if source_url:
        md.append(f'source_url: "{source_url}"')
    md.append("tags:")
    md.append("  - recipe")
    md.append("  - paprika")
    for cat in cat_names:
        clean_tag = slugify(cat)
        if clean_tag:
            md.append(f"  - recipe/{clean_tag}")
    if cat_names:
        md.append("categories:")
        for cat in cat_names:
            md.append(f'  - "{cat}"')
    md.append("---\n")

    md.append(f"# 🍲 {name}\n")

    meta_parts = []
    if prep_time:
        meta_parts.append(f"**Prep**: {prep_time}")
    if cook_time:
        meta_parts.append(f"**Cook**: {cook_time}")
    if servings:
        meta_parts.append(f"**Servings**: {servings}")
    if cat_names:
        meta_parts.append(f"**Category**: {', '.join(cat_names)}")
    if meta_parts:
        md.append(f"* {' | '.join(meta_parts)} *\n")

    if description_raw.strip():
        md.append(f"{description_raw.strip()}\n")

    if ingredients_raw.strip():
        md.append("## 🛒 Ingredients\n")
        for line in ingredients_raw.strip().splitlines():
            line_str = line.strip()
            if line_str:
                md.append(f"- {line_str}")
        md.append("")

    if directions_raw.strip():
        md.append("## 👩‍🍳 Directions\n")
        step_num = 1
        for line in directions_raw.strip().splitlines():
            line_str = line.strip()
            if line_str:
                if re.match(r"^\d+[\.\)]", line_str):
                    md.append(line_str)
                else:
                    md.append(f"{step_num}. {line_str}")
                    step_num += 1
        md.append("")

    if notes_raw.strip():
        md.append("## 📝 Notes\n")
        md.append(f"{notes_raw.strip()}\n")

    return "\n".join(md)


def sync_paprika(vault_dir, dry_run=False, force=False):
    email, password = load_credentials()
    cache = load_cache()
    cached_hashes = cache.get("recipe_hashes", {})

    session = requests.Session()
    session.auth = (email, password)

    print("🍳 Connecting to Paprika Cloud Sync...")
    category_map = get_categories(session)
    print(f"  ✓ Discovered {len(category_map)} categories: {', '.join(category_map.values())}")

    # 1. Sync Recipes
    res = session.get(f"{BASE_URL}/recipes/", timeout=20)
    if res.status_code != 200:
        print(f"❌ Failed to fetch recipes: HTTP {res.status_code}")
        sys.exit(1)

    recipes_meta = res.json().get("result", [])
    print(f"  ✓ Discovered {len(recipes_meta)} recipes in Paprika library.")

    recipes_dir = os.path.join(vault_dir, "Recipes")
    if not dry_run:
        os.makedirs(recipes_dir, exist_ok=True)

    synced_count = 0
    skipped_count = 0

    for r_meta in recipes_meta:
        uid = r_meta.get("uid")
        server_hash = r_meta.get("hash")
        name = r_meta.get("name") or "untitled"

        if not force and cached_hashes.get(uid) == server_hash:
            skipped_count += 1
            continue

        r_res = session.get(f"{BASE_URL}/recipe/{uid}/", timeout=15)
        if r_res.status_code != 200:
            print(f"  ⚠️ Failed to fetch recipe {uid}: HTTP {r_res.status_code}")
            continue

        detail = r_res.json().get("result", {})
        recipe_name = detail.get("name", name)
        slug = slugify(recipe_name)
        if not slug:
            slug = f"recipe-{uid[:8]}"
        filename = f"{slug}.md"
        filepath = os.path.join(recipes_dir, filename)

        md_content = render_recipe_markdown(detail, category_map)

        if not dry_run:
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(md_content)
            cached_hashes[uid] = server_hash
        synced_count += 1
        print(f"  + Synced: {recipe_name} -> {filename}")

    if not dry_run:
        cache["recipe_hashes"] = cached_hashes
        save_cache(cache)

    print(f"✅ Recipes sync complete ({synced_count} written, {skipped_count} unchanged up-to-date).")

    # 2. Sync Meal Planner
    sync_dir = os.path.join(vault_dir, "_Sync")
    if not dry_run:
        os.makedirs(sync_dir, exist_ok=True)

    m_res = session.get(f"{BASE_URL}/meals/", timeout=15)
    if m_res.status_code == 200:
        meals = m_res.json().get("result", [])
        meals_md = [
            "# 📅 Paprika Scheduled Meals\n",
            f"*Last synchronized: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}*\n"
        ]
        if not meals:
            meals_md.append("*No scheduled meals currently in Paprika meal planner.*\n")
        else:
            sorted_meals = sorted(meals, key=lambda m: m.get("date", ""))
            for m in sorted_meals:
                m_date = m.get("date", "")
                m_type = m.get("meal_type", "Dinner")
                m_name = m.get("name", "Planned Meal")
                meals_md.append(f"- **{m_date}** ({m_type}): [[Recipes/{slugify(m_name)}|{m_name}]]")
            meals_md.append("")

        if not dry_run:
            meals_path = os.path.join(sync_dir, "paprika-meals.md")
            with open(meals_path, "w", encoding="utf-8") as f:
                f.write("\n".join(meals_md))
            print(f"  ✓ Written meal planner to {meals_path} ({len(meals)} meals)")

    # 3. Sync Groceries
    g_res = session.get(f"{BASE_URL}/groceries/", timeout=15)
    if g_res.status_code == 200:
        groceries = g_res.json().get("result", [])
        active_items = [g for g in groceries if not g.get("purchased")]
        groc_md = [
            "# 🛒 Paprika Recipe Groceries\n",
            f"*Last synchronized: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}*\n"
        ]
        if not active_items:
            groc_md.append("*No active grocery items in Paprika.*\n")
        else:
            for g in active_items:
                groc_md.append(f"- [ ] {g.get('name')}")
            groc_md.append("")

        if not dry_run:
            groc_path = os.path.join(sync_dir, "paprika-groceries.md")
            with open(groc_path, "w", encoding="utf-8") as f:
                f.write("\n".join(groc_md))
            print(f"  ✓ Written active groceries to {groc_path} ({len(active_items)} items)")


def main():
    parser = argparse.ArgumentParser(description="Sync Paprika Recipe Manager recipes, meals, and groceries to Obsidian.")
    parser.add_argument("--vault-dir", default=DEFAULT_VAULT_DIR, help=f"Path to Obsidian Vault root (default: {DEFAULT_VAULT_DIR})")
    parser.add_argument("--dry-run", action="store_true", help="Print actions without modifying vault files.")
    parser.add_argument("--force", action="store_true", help="Force re-download and re-write of all recipes regardless of hash cache.")
    args = parser.parse_args()

    sync_paprika(args.vault_dir, dry_run=args.dry_run, force=args.force)


if __name__ == "__main__":
    main()
