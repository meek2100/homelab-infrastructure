"""
title: Obsidian Vault & Recipe Reader
author: homelab
author_url: https://github.com/meek2100/homelab-infrastructure
git_url: https://github.com/meek2100/homelab-infrastructure
description: Query, search, and view recipes, meal calendars, maintenance records, and family notes directly from your private Obsidian vault
version: 1.0.0
requirements: pydantic
"""

import os
import glob
from typing import Optional, List
from pydantic import BaseModel, Field


class Tools:
    class Valves(BaseModel):
        VAULT_DIR: str = Field(
            default="/mnt/c/Users/dtheurer/Obsidian/Vault/Personal",
            description="Absolute path to personal Obsidian vault root"
        )

    def __init__(self):
        self.valves = self.Valves()

    def search_recipes(
        self,
        query: str,
        category: Optional[str] = None
    ) -> str:
        """
        Search private Paprika recipes by ingredient, recipe title, or keywords.
        :param query: Search term (e.g., 'chicken', 'cookies', 'crockpot', 'garlic').
        :param category: Optional category filter (e.g., 'Crockpot Dinners', 'Cookies').
        :return: Matching recipes with ingredients summary and rating.
        """
        recipes_dir = os.path.join(self.valves.VAULT_DIR, "Recipes")
        if not os.path.exists(recipes_dir):
            return f"Error: Recipes directory {recipes_dir} not found."

        query_lower = query.lower()
        matches = []

        for fpath in glob.glob(os.path.join(recipes_dir, "*.md")):
            try:
                with open(fpath, "r", encoding="utf-8") as f:
                    content = f.read()

                title = os.path.basename(fpath).replace(".md", "").replace("-", " ").title()
                # Extract title from markdown header if available
                for line in content.splitlines():
                    if line.startswith("# ") and not line.startswith("# 🍲") and not line.startswith("# 🍽️"):
                        title = line.replace("#", "").strip()
                        break
                    elif line.startswith("# "):
                        title = line.replace("#", "").strip()

                content_lower = content.lower()
                if query_lower in content_lower:
                    if category and category.lower() not in content_lower:
                        continue

                    # Extract prep/cook time if available
                    time_info = ""
                    for line in content.splitlines()[:25]:
                        if "cook_time:" in line or "prep_time:" in line:
                            time_info += f" | {line.strip()}"

                    matches.append(f"• **{title}** (`{os.path.basename(fpath)}`){time_info}")
            except Exception:
                continue

        if not matches:
            return f"No recipes found matching '{query}'" + (f" in category '{category}'" if category else "") + "."

        return f"Found {len(matches)} matching recipes:\n" + "\n".join(matches[:15])

    def get_recipe_details(
        self,
        recipe_filename: str
    ) -> str:
        """
        Retrieve the full ingredients, cook times, and instructions for a specific recipe.
        :param recipe_filename: Filename of the recipe (e.g. 'chicken-gnocchi-soup.md' or 'chicken-gnocchi-soup').
        :return: Full markdown content of the recipe.
        """
        if not recipe_filename.endswith(".md"):
            recipe_filename += ".md"

        fpath = os.path.join(self.valves.VAULT_DIR, "Recipes", recipe_filename)
        if not os.path.exists(fpath):
            # Try fuzzy match
            base = recipe_filename.replace(".md", "").lower()
            found = None
            for p in glob.glob(os.path.join(self.valves.VAULT_DIR, "Recipes", "*.md")):
                if base in os.path.basename(p).lower():
                    found = p
                    break
            if found:
                fpath = found
            else:
                return f"Error: Recipe file '{recipe_filename}' not found in {os.path.join(self.valves.VAULT_DIR, 'Recipes')}."

        try:
            with open(fpath, "r", encoding="utf-8") as f:
                return f.read()
        except Exception as e:
            return f"Error reading recipe file: {e}"

    def get_maintenance_due(
        self
    ) -> str:
        """
        Check upcoming and seasonal home maintenance checklists and schedules.
        :return: Summary of home maintenance items on record.
        """
        maint_dir = os.path.join(self.valves.VAULT_DIR, "Maintenance")
        if not os.path.exists(maint_dir):
            return f"Error: Maintenance directory {maint_dir} not found."

        items = []
        for fpath in glob.glob(os.path.join(maint_dir, "*.md")):
            try:
                with open(fpath, "r", encoding="utf-8") as f:
                    content = f.read().strip()
                title = os.path.basename(fpath).replace(".md", "").replace("-", " ").title()
                items.append(f"### {title}\n{content[:500]}")
            except Exception:
                continue

        if not items:
            return "No maintenance checklists found."

        return f"Found {len(items)} maintenance records:\n\n" + "\n\n".join(items)
