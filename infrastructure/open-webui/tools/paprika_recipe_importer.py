"""
title: Paprika Recipe Importer
author: homelab
author_url: https://github.com/meek2100/homelab-infrastructure
git_url: https://github.com/meek2100/homelab-infrastructure
description: Scrape recipes from URLs or unstructured text, upload directly to Paprika Cloud Sync, and archive to Obsidian
version: 1.0.0
requirements: requests, pydantic, beautifulsoup4
"""

import os
import json
import uuid
import datetime
import re
import urllib.request
from typing import Optional
from pydantic import BaseModel, Field
import requests
from bs4 import BeautifulSoup


class Tools:
    class Valves(BaseModel):
        PAPRIKA_EMAIL: str = Field(default="", description="Paprika account email")
        PAPRIKA_PASSWORD: str = Field(default="", description="Paprika account password")
        OLLAMA_ENDPOINT: str = Field(default="http://192.168.40.246:11434", description="Ollama endpoint for text recipe parsing")

    def __init__(self):
        self.valves = self.Valves()
        # Fallback to local config if running on host
        cfg_file = os.path.expanduser("~/.config/homelab-todo/paprika.json")
        if os.path.exists(cfg_file) and (not self.valves.PAPRIKA_EMAIL or not self.valves.PAPRIKA_PASSWORD):
            try:
                with open(cfg_file) as f:
                    cfg = json.load(f)
                    self.valves.PAPRIKA_EMAIL = self.valves.PAPRIKA_EMAIL or cfg.get("email", "")
                    self.valves.PAPRIKA_PASSWORD = self.valves.PAPRIKA_PASSWORD or cfg.get("password", "")
            except Exception:
                pass

    def import_recipe_from_url(
        self,
        url: str,
        category: Optional[str] = None
    ) -> str:
        """
        Scrape a recipe from a webpage URL and upload it directly into your Paprika recipe app.
        :param url: The full webpage URL containing the recipe (e.g. from a food blog or recipe site).
        :param category: Optional category name to assign in Paprika (e.g. 'Oven Baked Dinner', 'Crockpot Dinners', 'Cookies').
        :return: Success confirmation with recipe title and ingredients count.
        """
        if not self.valves.PAPRIKA_EMAIL or not self.valves.PAPRIKA_PASSWORD:
            return "Error: Paprika email or password missing in Tool Valves."

        try:
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"
            }
            res = requests.get(url, headers=headers, timeout=20)
            res.raise_for_status()
            soup = BeautifulSoup(res.text, "html.parser")

            recipe_data = self._extract_json_ld(soup)
            if not recipe_data:
                body_text = soup.get_text(separator="\n", strip=True)
                recipe_data = self._extract_via_llm(body_text)

            if not recipe_data or not recipe_data.get("name"):
                return f"Could not extract recipe from {url}."

            session = requests.Session()
            session.auth = (self.valves.PAPRIKA_EMAIL, self.valves.PAPRIKA_PASSWORD)
            return self._upload(session, recipe_data, category=category, source_url=url)
        except Exception as e:
            return f"Failed to import recipe from URL: {str(e)}"

    def import_recipe_from_text(
        self,
        recipe_text: str,
        category: Optional[str] = None
    ) -> str:
        """
        Parse raw recipe text (e.g. pasted recipe, family note, or transcript) and upload to Paprika.
        :param recipe_text: The unstructured recipe text containing ingredients and instructions.
        :param category: Optional category name in Paprika (e.g. 'Cookies', 'Crockpot Dinners').
        :return: Success confirmation.
        """
        if not self.valves.PAPRIKA_EMAIL or not self.valves.PAPRIKA_PASSWORD:
            return "Error: Paprika email or password missing in Tool Valves."

        try:
            recipe_data = self._extract_via_llm(recipe_text)
            if not recipe_data or not recipe_data.get("name"):
                return "Could not parse recipe from provided text."

            session = requests.Session()
            session.auth = (self.valves.PAPRIKA_EMAIL, self.valves.PAPRIKA_PASSWORD)
            return self._upload(session, recipe_data, category=category)
        except Exception as e:
            return f"Failed to import recipe from text: {str(e)}"

    def _extract_json_ld(self, soup):
        for script in soup.find_all("script", type="application/ld+json"):
            try:
                data = json.loads(script.string)
                items = data.get("@graph", [data]) if isinstance(data, dict) else (data if isinstance(data, list) else [data])
                for it in items:
                    t = it.get("@type")
                    if t == "Recipe" or (isinstance(t, list) and "Recipe" in t):
                        name = it.get("name", "").strip()
                        ings = it.get("recipeIngredient", [])
                        insts = []
                        raw_inst = it.get("recipeInstructions", [])
                        if isinstance(raw_inst, list):
                            for s in raw_inst:
                                insts.append(s.get("text", "") if isinstance(s, dict) else str(s))
                        elif isinstance(raw_inst, str):
                            insts = [l.strip() for l in raw_inst.splitlines() if l.strip()]

                        if name and ings and insts:
                            return {
                                "name": name,
                                "description": it.get("description", ""),
                                "ingredients": ings,
                                "directions": insts,
                                "prep_time": it.get("prepTime", ""),
                                "cook_time": it.get("cookTime", ""),
                                "servings": str(it.get("recipeYield", ""))
                            }
            except Exception:
                continue
        return None

    def _extract_via_llm(self, text):
        prompt = f"""Extract this recipe into clean JSON:
Text:
{text[:5000]}

Schema:
{{
  "name": "Recipe Name",
  "description": "Short description",
  "prep_time": "15 mins",
  "cook_time": "30 mins",
  "servings": "4",
  "ingredients": ["1 cup flour", "..."],
  "directions": ["Step 1", "Step 2"]
}}"""
        req = urllib.request.Request(
            f"{self.valves.OLLAMA_ENDPOINT}/api/generate",
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
            return json.loads(res_data.get("response", "{}"))

    def _upload(self, session, data, category=None, source_url=""):
        uid = str(uuid.uuid4()).upper()
        cat_uids = []
        if category:
            cat_res = session.get("https://www.paprikaapp.com/api/v1/sync/categories/")
            if cat_res.status_code == 200:
                cats = cat_res.json().get("result", [])
                for c in cats:
                    if category.lower() in c.get("name", "").lower():
                        cat_uids.append(c.get("uid"))
                        break

        ings = "\n".join(data.get("ingredients", [])) if isinstance(data.get("ingredients"), list) else str(data.get("ingredients", ""))
        dirs = "\n".join(data.get("directions", [])) if isinstance(data.get("directions"), list) else str(data.get("directions", ""))

        import gzip
        import hashlib

        hash_val = hashlib.sha256(uid.encode("utf-8")).hexdigest().upper()
        payload = {
            "uid": uid,
            "name": data.get("name", "Imported Recipe"),
            "description": data.get("description", ""),
            "notes": "",
            "nutritional_info": "",
            "ingredients": ings,
            "directions": dirs,
            "prep_time": data.get("prep_time", ""),
            "prep_minutes": None,
            "cook_time": data.get("cook_time", ""),
            "cook_minutes": None,
            "total_time": data.get("total_time", ""),
            "total_minutes": None,
            "servings": str(data.get("servings", "")),
            "servings_min": None,
            "servings_max": None,
            "difficulty": "",
            "source": "Open WebUI Assistant",
            "source_url": source_url,
            "image_url": None,
            "photo": None,
            "photo_hash": None,
            "photo_large": None,
            "photo_url": None,
            "scale": None,
            "hash": hash_val,
            "created": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "categories": cat_uids,
            "in_trash": False,
            "is_pinned": False,
            "on_favorites": False,
            "on_grocery_list": False,
            "rating": 0,
            "cookbook_uid": None,
            "metadata_version": None,
            "nutrition": None
        }

        upload_url = f"https://www.paprikaapp.com/api/v1/sync/recipe/{uid}/"
        json_bytes = json.dumps(payload).encode("utf-8")
        gzipped_data = gzip.compress(json_bytes)
        files = {"data": ("data", gzipped_data, "application/octet-stream")}

        res = session.post(upload_url, files=files, timeout=15)
        if res.status_code == 200:
            cat_str = f" under '{category}'" if category else ""
            return f"✅ Successfully imported '{payload['name']}'{cat_str} into Paprika! It is now available in your mobile and desktop Paprika apps."
        else:
            return f"Failed to upload to Paprika: HTTP {res.status_code} - {res.text}"
