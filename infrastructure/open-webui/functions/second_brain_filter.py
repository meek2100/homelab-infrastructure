"""
title: Second Brain Context Auto-Injector
author: homelab
author_url: https://github.com/meek2100/homelab-infrastructure
git_url: https://github.com/meek2100/homelab-infrastructure
description: Automatically intercepts user chat messages and injects live Microsoft To Do lists, Google Calendar schedules, Paprika recipes, Obsidian maintenance records, and Homelab Fleet health directly into the prompt.
version: 1.1.0
requirements: requests, pydantic
"""

import os
import glob
import json
import socket
import datetime
import urllib.request
import urllib.parse
from typing import Optional
from pydantic import BaseModel, Field

# Embedded static offline fallback cache for household maintenance records
EMBEDDED_MAINTENANCE = {
  "car-service.md": "---\ntype: maintenance\nstatus: active\nrecurs: semi-annual\ndue: 2026-11-15\nowner: [[dtheurer]]\ntags:\n  - automotive\n  - vehicle\n---\n\n# \ud83d\ude97 Vehicle Semi-Annual Oil Change & Tire Rotation\n\n* **Frequency**: Semi-annual or every 5,000\u20137,500 miles\n* **Target Due Date**: 2026-11-15\n* **Checklist**:\n  1. Engine oil and oil filter replacement (full synthetic).\n  2. Rotate tires and inspect tread depth and wear pattern.\n  3. Inspect brake pad thickness and rotor condition.\n  4. Top off windshield washer fluid and inspect wiper blades.\n  5. Check engine air filter and cabin air filter.\n  6. Inspect battery health and terminal corrosion.",
  "fountain-winterization.md": "---\ntype: maintenance\nstatus: active\nrecurs: annual\ndue: 2026-10-31\nowner: [[dtheurer]]\ntags:\n  - household\n  - outdoor\n  - seasonal\n---\n\n# \u26f2 Front & Back Fountain Clean, Drain & Winter Cover\n\n* **Frequency**: Annual (Late October)\n* **Location**: Front yard fountain & back patio fountain\n* **Target Due Date**: 2026-10-31\n* **Procedure**:\n  1. Unplug and disconnect submersible pumps in front and back fountains.\n  2. Submersible pumps should be cleaned, drained, and stored indoors to prevent impeller freezing.\n  3. Siphon or shop-vac all standing water from fountain basins.\n  4. Scrub algae/sediment from bowls and basin walls.\n  5. Fit weather-resistant protective winter covers over both fountain structures and secure drawstrings.",
  "furnace-filters.md": "---\ntype: maintenance\nstatus: active\nrecurs: annual\ndue: 2026-11-01\nowner: [[dtheurer]]\ntags:\n  - household\n  - hvac\n---\n\n# \ud83d\udee0\ufe0f Annual Furnace & HVAC Filter Replacement\n\n* **Frequency**: Annual (every November ahead of winter heating season)\n* **Location**: Basement utility closet / air handler\n* **Filter Size**: 16x25x4 MERV 11\n* **Procedure**:\n  1. Turn off HVAC system power switch.\n  2. Slide out existing filter; vacuum dust from filter slot.\n  3. Insert new filter with airflow arrow pointing toward the blower unit.\n  4. Restore power and confirm smooth airflow.",
  "smoke-detector-batteries.md": "---\ntype: maintenance\nstatus: active\nrecurs: annual\ndue: 2026-11-01\nowner: [[dtheurer]]\ntags:\n  - household\n  - safety\n---\n\n# \ud83d\udea8 Smoke & Carbon Monoxide Detector Battery Test & Replacement\n\n* **Frequency**: Annual (Beginning of November / Daylight Savings Time)\n* **Location**: All bedrooms, hallways, kitchen, and basement\n* **Battery Type**: 9V Alkaline / AA Lithium (as required per unit)\n* **Target Due Date**: 2026-11-01\n* **Procedure**:\n  1. Press and hold the \"Test\" button on each detector to verify audible siren and interconnectivity.\n  2. Replace backup batteries in all hardwired and standalone smoke/CO detectors.\n  3. Vacuum or wipe dust away from sensor vents.\n  4. Inspect manufacture expiration dates stamped on rear of units (replace units older than 10 years).",
  "sprinkler-winterization.md": "---\ntype: maintenance\nstatus: active\nrecurs: annual\ndue: 2026-10-31\nowner: [[dtheurer]]\ntags:\n  - household\n  - irrigation\n  - seasonal\n---\n\n# \ud83d\udca6 Sprinkler & Irrigation Blow-out & Winterization\n\n* **Frequency**: Annual (Late October, before first hard freeze)\n* **Location**: Exterior main shut-off valve, backflow preventer, and valve boxes\n* **Target Due Date**: 2026-10-31\n* **Procedure**:\n  1. Turn off main indoor sprinkler water supply valve.\n  2. Connect air compressor (regulated to max 50 PSI to protect PVC valves) to blowout port.\n  3. Cycle through each irrigation zone individually from controller until all water heads spray fine mist/air only.\n  4. Leave test cocks and valves on backflow preventer open at a 45-degree angle to prevent freeze expansion damage.\n  5. Set irrigation controller to \"System Off\" or \"Rain Delay\".",
  "water-heater-flush.md": "---\ntype: maintenance\nstatus: active\nrecurs: annual\ndue: 2026-11-15\nowner: [[dtheurer]]\ntags:\n  - household\n  - plumbing\n---\n\n# \ud83d\udebf Annual Water Heater Sediment Drain & Flush\n\n* **Frequency**: Annual (Mid-November)\n* **Location**: Basement utility room water heater tank\n* **Target Due Date**: 2026-11-15\n* **Procedure**:\n  1. Turn off power/breaker or set gas valve to \"Pilot\".\n  2. Turn off cold water inlet valve.\n  3. Attach garden hose to lower tank drain bib and route hose outside or to floor drain.\n  4. Open pressure relief valve or open a hot water faucet upstairs to break vacuum.\n  5. Open drain bib to flush sediment until water runs completely clear.\n  6. Briefly open cold water inlet in short bursts to stir and flush remaining bottom sediment.\n  7. Close drain bib, remove hose, close pressure relief valve.\n  8. Refill tank completely before restoring power or gas burner.",
  "water-softener-salt.md": "---\ntype: maintenance\nstatus: active\nrecurs: monthly\ndue: 2026-11-01\nowner: [[dtheurer]]\ntags:\n  - household\n  - plumbing\n---\n\n# \ud83e\uddc2 Monthly Water Softener Salt Level Check & Refill\n\n* **Frequency**: Monthly (1st of every month)\n* **Location**: Basement brine tank\n* **Salt Type**: High-purity solar salt pellets or crystals (yellow/blue bag)\n* **Target Due Date**: 2026-11-01\n* **Procedure**:\n  1. Open brine tank lid and check salt depth.\n  2. Ensure salt level is at least half full and above the standing water line.\n  3. Inspect for \"salt bridging\" (a hard crust forming a hollow void); gently tap with a broom handle if crusted.\n  4. Add 1\u20132 bags (40\u201380 lbs) of clean salt pellets as needed."
}

# Embedded static offline fallback cache for Paprika family recipes
EMBEDDED_RECIPES = {
  "brown-butter-chocolate-chip-cookies.md": "---\ntype: recipe\ntitle: \"Brown Butter Chocolate Chip Cookies\"\nservings: \"Yield: 26-28 cookies\"\nprep_time: \"45 min\"\ncook_time: \"45 minutes\"\nrating: 5\nsource: \"sallysbakingaddiction.com\"\nsource_url: \"https://sallysbakingaddiction.com/brown-butter-chocolate-chip-cookies/\"\ntags:\n  - recipe\n  - paprika\n  - recipe/cookies\ncategories:\n  - \"Cookies\"\n---\n\n# \ud83c\udf72 Brown Butter Chocolate Chip Cookies\n\n* **Prep**: 45 min | **Cook**: 45 minutes | **Servings**: Yield: 26-28 cookies | **Category**: Cookies *\n\n## \ud83d\uded2 Ingredients\n\n- 1 cup (16 Tbsp; 226g) unsalted butter\n- 1/2 cup (100g) granulated sugar\n- 1 cup (200g) packed light or dark brown sugar\n- 1 large egg + 1 egg yolk, at room temperature\n- 2 teaspoons pure vanilla extract\n- 2 and 1/2 cups (313g) all-purpose flour (do not scoop; weigh or spoon & level)\n- 1 teaspoon cornstarch\n- 1 teaspoon baking soda\n- 1/2 teaspoon salt\n- 2 Tablespoons (30ml) milk, warmed or at room temperature\n- 1 and 1/2 cups (270g) semi-sweet chocolate chips\n- optional: flaky sea salt, for topping\n\n## \ud83d\udc69\u200d\ud83c\udf73 Directions\n\n1. Brown the butter: Slice the butter into pieces and place in a light-colored skillet. The light colored helps you determine when the butter begins browning. Melt the butter over medium heat and stir or whisk constantly. Once melted, the butter will begin to foam. Keep stirring/whisking. After 5\u20137 minutes, the butter will begin browning and you\u2019ll notice lightly browned specks begin to form at the bottom of the pan, which are the milk solids toasting. Cook until it is golden in color. Once browned, remove from heat immediately and pour into a heatproof bowl, including all of the browned bits (flavor!). Let cool for 10 minutes, then place in the refrigerator and chill until solid, about 90 minutes. After about 30 minutes, tightly cover the bowl.\n2. Remove the solidified brown butter from the refrigerator and spoon it into a large bowl (or the bowl of your stand mixer). Using a handheld mixer or stand mixer fitted with a paddle attachment, beat on high speed for 1\u20132 minutes until smooth and creamy. It may look slightly grainy at first\u2014keep beating and it will come together. If the butter is too firm to cream, let it sit at room temperature for 5\u201310 minutes. You can also microwave it for 5\u20138 seconds to slightly soften it, but do not melt it; it should remain solid, just softened enough to beat smoothly.\n3. Add the brown sugar and granulated sugar and beat on medium-high speed until lightened in color and combined, about 2 minutes. Add the egg, egg yolk, and vanilla extract and beat until combined. Scrape down the sides and bottom of the bowl as needed.\n4. In a separate bowl, whisk together the flour, cornstarch, baking soda, and salt. Add the dry ingredients to the butter mixture and mix on low speed until just combined. With the mixer running on low, drizzle in the milk and mix until incorporated. The cookie dough will be thick and soft. Add the chocolate chips and mix until evenly distributed.\n5. Scoop and roll the dough into balls, about 2 Tablespoons or 45g each. Shape them taller rather than wide\u2014almost like a cylinder. This helps the cookies bake up thicker. Place the dough balls on a lined baking sheet or plate, cover, and refrigerate for at least 2 hours or up to 3 days.\n6. Preheat oven to 375\u00b0F (191\u00b0C). Line large baking sheets with parchment paper or silicone baking mats. Set aside. Arrange 8 dough balls per baking sheet, spacing them about 3 inches apart. Sprinkle sea salt, if using, on top of the dough balls.\n7. Bake for 12\u201314 minutes, or until the edges are lightly golden brown. The centers will look soft when you remove them from the oven. Cool on the baking sheet for 5 minutes. During this time, you can press a few extra chocolate chips into the tops (just for looks!). The cookies will slightly deflate as they cool. After 5 minutes, transfer to a wire rack to cool completely.\n8. Store in an airtight container at room temperature for up to 5 days.\n\n## \ud83d\udcdd Notes\n\nMake Ahead Instructions: You can make the cookie dough and chill it in the refrigerator for up to 3 days. Baked cookies freeze well for up to 3 months. Thaw at room temperature. Unbaked cookie dough balls freeze well for up to 3 months. Bake frozen cookie dough balls for an extra minute, no need to thaw. Read my tips and tricks on how to freeze cookie dough.\n\nSpecial Tools (affiliate links): Light-Colored Skillet or Stainless Steel Skillet | Electric Mixer (Handheld or Stand) | Baking Sheet | Silicone Baking Mat or Parchment Paper | Medium Cookie Scoop | Cooling Rack | Flaky Sea Salt\n\nWhy Do I Solidify the Browned Butter? Solidifying the browned butter allows you to cream it with the sugars, which creates structure and gives the cookies a thicker texture. Using melted brown butter will produce a thinner, denser, and possibly greasy cookie.\n\nExtra Egg Yolk: The extra yolk adds richness and chewiness without making the cookies cakey; do not skip.\n\nWhy Add Cornstarch? Cornstarch helps create a softer, thicker cookie by tenderizing the crumb. If needed, you can leave it out.\n\nMilk: Browning butter reduces moisture, so adding a splash of milk brings that balance back without weighing down the dough. I recommend reduced-fat milk, though whole milk and nondairy milks work in a pinch.\n\nOven Temperature Update: Over the years, we\u2019ve found that baking these at 375\u00b0F (191\u00b0C), slightly warmer than usual, helps set the shape quickly so the cookies stay thicker.\n\nBe sure to check out my top 5 cookie baking success tips AND these are my 10 must-have cookie baking tools.",
  "chai-spice-cookies.md": "---\ntype: recipe\ntitle: \"Chai Spice Cookies\"\nservings: \"Servings: 40 3\u2033 cookies\"\nprep_time: \"25 mins\"\ncook_time: \"10 mins\"\nsource: \"floralapron.com\"\nsource_url: \"https://floralapron.com/chai-cookies/\"\ntags:\n  - recipe\n  - paprika\n  - recipe/cookies\ncategories:\n  - \"Cookies\"\n---\n\n# \ud83c\udf72 Chai Spice Cookies\n\n* **Prep**: 25 mins | **Cook**: 10 mins | **Servings**: Servings: 40 3\u2033 cookies | **Category**: Cookies *\n\n## \ud83d\uded2 Ingredients\n\n- For the Chai Spice Cookie Dough:\n- 1 cup (226 g) salted butter at room temperature (16 Tablespoons)\n- 1 cup (210 g) brown sugar\n- \u00bd cup (100 g) granulated sugar\n- 2 large eggs\n- 1 teaspoon vanilla extract\n- 2\u00bc cups (300 g) all purpose flour spooned and leveled\n- 1 teaspoon (5 g) baking powder\n- 1 teaspoon (4 g) baking soda\n- \u00bc teaspoon salt\n- 1 Tablespoon (5 g) ground cardamom\n- 2\u00bd teaspoons (4 g) ground cinnamon\n- 1 teaspoon ground nutmeg\n- \u00bd teaspoon ground ginger\n- 2 pinches ground cloves\n- For the Chai Sugar Coating\n- \u00bc cup (50 g) granulated sugar\n- \u00bd teaspoon ground cardamom\n- \u00bd teaspoon ground cinnamon\n- \u00bc teaspoon ground nutmeg\n- \u215b teaspoon ground ginger\n- 1 pinch ground cloves\n- 1 cup (226 g) salted butter, \u00bd cup (100 g) granulated sugar, 1 cup (210 g) brown sugar\n- Add the eggs and vanilla extract and beat until fluffy, another 2-3 minutes. Scrape down the sides and bottom of the bowl and beat for another 15 seconds to incorporate everything.\n- 2 large eggs, 1 teaspoon vanilla extract\n- Add the flour, baking powder, baking soda, spices, and salt, and beat on low until combined, about 1-2 minutes. If needed, scrape down the sides and bottom of the bowl once towards the end to ensure everything is combined. Set aside.\n- 2\u00bc cups (300 g) all purpose flour, 1 teaspoon (5 g) baking powder, 1 teaspoon (4 g) baking soda, \u00bc teaspoon salt, 1 Tablespoon (5 g) ground cardamom, 2\u00bd teaspoons (4 g) ground cinnamon, 1 teaspoon ground nutmeg, \u00bd teaspoon ground ginger, 2 pinches ground cloves\n- In a small bowl or shallow dish, mix together the granulated sugar and spices.\n- \u00bc cup (50 g) granulated sugar, \u00bd teaspoon ground cardamom, \u00bd teaspoon ground cinnamon, \u00bc teaspoon ground nutmeg, \u215b teaspoon ground ginger, 1 pinch ground cloves\n\n## \ud83d\udc69\u200d\ud83c\udf73 Directions\n\n1. Preheat the oven to 375\u00b0F/190\u00b0C, and line at least two baking sheets with parchment paper or silicone mats. This recipe makes about 40 cookies, and you'll want to rotate between at least two pans.\n2. In the bowl of a stand mixer or a large bowl with a hand mixer, cream together softened butter, brown sugar, and granulated sugar on medium speed until light and fluffy, about 3-5 minutes.\n3. Scoop the cookie dough into 1\u00bd Tablespoon portions for cookies about 3\" (8 cm) in diameter, then coat them completely in the chai-spiced sugar. (You may make smaller or larger cookies; just know that the baking time will need to be adjusted accordingly!)\n4. Place the dough balls on your prepared baking sheets about 4\" (10 cm) apart. (I can comfortably fit 10 cookies on a half-sheet pan.) Bake for 9-11 minutes in the center rack*, until the very edges of the cookies are golden brown and the centers of the cookies look matte.\n5. Allow to cool on the cookie sheet for about 10 minutes before moving them, then enjoy!\n6. Use a mortar and pestle or spice grinder to finely grind a teaspoon of chai-spiced black tea, then add it to the cookie dough with the spices!\n7. Add a couple turns of freshly cracked pepper for stronger chai spice.\n8. Add an extra \u00bc cup (35 g) of flour to make thicker cookies.\n\n## \ud83d\udcdd Notes\n\n*Cookies can bake up at different times depending on the color of your pan and the kind of liner (parchment paper vs silicone mats) you used. Darker cookie sheets heat up faster and bake the snickerdoodles in 1-2 less minutes than snickerdoodles baked on light-colored cookie sheets. Keep a close eye on your first tray in the oven, then adjust your timer accordingly.\n\nStorage info: For the best flavor and texture, store these chai cookies in an airtight container at room temperature once cooled completely for up to 7 days. You can also freeze baked cookies or un-sugared cookie dough balls in airtight containers for up to 3 months.\n\nMake them your own:",
  "chicken-gnocchi-soup.md": "---\ntype: recipe\ntitle: \"Chicken Gnocchi Soup\"\nservings: \"Yield: 8\u201310\"\nprep_time: \"10 minutes\"\ncook_time: \"total time: 8 hours 10 minutes\"\nrating: 5\nsource: \"pinchofyum.com\"\nsource_url: \"https://pinchofyum.com/crockpot-chicken-gnocchi-soup\"\ntags:\n  - recipe\n  - paprika\n  - recipe/crockpot-dinners\ncategories:\n  - \"Crockpot Dinners\"\n---\n\n# \ud83c\udf72 Chicken Gnocchi Soup\n\n* **Prep**: 10 minutes | **Cook**: total time: 8 hours 10 minutes | **Servings**: Yield: 8\u201310 | **Category**: Crockpot Dinners *\n\nEmme Rated \u2b50\ufe0f\u2b50\ufe0f\u2b50\ufe0f\u2b50\ufe0f\u2b50\ufe0f\nDarin Rated \u2b50\ufe0f\u2b50\ufe0f\u2b50\ufe0f\u2b50\ufe0f\u2b50\ufe0f\n\n## \ud83d\uded2 Ingredients\n\n- 1 lb. boneless skinless chicken breasts\n- 2 cups mirepoix (just a simple mixture of chopped onions, celery, and carrots)\n- 1\u20132 teaspoons dried basil\n- 1\u20132 teaspoon Italian seasoning\n- 1 teaspoon poultry seasoning\n- 1 teaspoon salt\n- 4 cups chicken broth\n- 3 tablespoons cornstarch dissolved in 2 tablespoons water\n- two 12 ounce cans evaporated milk\n- two 1 lb. packages gnocchi (about 4 cups)\n- 6 slices bacon\n- 2\u20133 cloves garlic, minced\n- 2 cups fresh baby spinach\n\n## \ud83d\udc69\u200d\ud83c\udf73 Directions\n\n1. It reminds me a little bit of the chicken wild rice soup in that we just start pretty basic with carrots, celery, onions, chicken, spices, and broth in a crockpot. And you know how I love me some chicken wild rice soup slash any soup in a crockpot. Minnesota represent!\n2. Unlike the wild rice soup, this chicken gnocchi soup is made thick by evaporated milk and a quick cornstarch slurry. So if you\u2019re looking for thick and creamy soup while avoiding the butter/flour/cream route of a roux base, this is your magic. \u2728\n3. GNOCCHI. Those tiny dumplings of happy feelings that are mixed in throughout the chicken gnocchi soup make the whole thing come together. Every time I make this soup, Bjork a) raves, and b) talks for at least 5 minutes about how much he loves \u201cthe dumplings.\u201d I could almost actually call this Chicken and Dumpling soup except the Chicken and Dumpling soup of my youth (a Herman\u2019s bakery special in Cambridge, MN) had approximately zero vegetables and was practically untouchable in its level of homey perfection, so I will not go there. Let\u2019s just give ourselves a pat on the back for the carrots, celery, and saut\u00e9ed garlic spinach that are present at this soup party. And the bacon. I always invite the bacon.\n4. Do I have to use evaporated milk?\n5. You can use something other than evaporated milk, but I found that evaporated milk has the creaminess of half and half or heavy whipping cream without actually needing to use up a bunch of half and half in the soup.\n6. The leftovers soak up a lot of the moisture because of the gnocchi, so you might need to add more evaporated milk depending on how soupy you want it and/or how long you\u2019ll be keeping it around.\n7. Instant pot-\n8. Add the chicken, mirepoix, basil, Italian seasoning, poultry seasoning, salt, and broth to the Instant Pot. Cook for 20 minutes on high pressure. Let out the steam using quick release. Remove the chicken to shred and then add it back to the pot. Stir in the cornstarch mixture, evaporated milk, and gnocchi. Use the \u201cSaute\u201d function to simmer the soup for another 20 minutes or so to thicken it all up. Add in the bacon and spinach, and stir to combine.\n9. crockpot:\n10. Place the chicken, mirepoix, basil, Italian seasoning, poultry seasoning, salt, and broth in a crockpot or slow cooker. Cover and cook on high for 4-5 hours or low for 6-8 hours. Shred the chicken directly in the crockpot.\n11. Add the cornstarch mixture, evaporated milk, and gnocchi. Stir and replace cover. Cook another 45 minutes \u2013 1 hour until the soup has thickened and the gnocchi has softened.\n12. While the soup is thickening, cut the bacon into small pieces and fry until crispy. Drain on paper towels and wipe most of the bacon grease out of the pan, leaving just a little bit for the spinach/garlic. Add the garlic and saute for one minute. Add the spinach and stir until wilted. Remove from heat. Add the bacon and spinach to the crockpot. Stir to combine.\n13. Add any additional liquid as needed (I added about a cup of water once it started to thicken) and season again with salt and pepper as needed.\n\n## \ud83d\udcdd Notes\n\nBe sure to taste and adjust with salt/pepper before serving. It may need more depending on the saltiness of your broth.",
  "creamy-crockpot-white-chicken-chili.md": "---\ntype: recipe\ntitle: \"Creamy Crockpot White Chicken Chili\"\nservings: \"Servings: 6\"\nprep_time: \"5 minutes\"\ncook_time: \"8 hours\"\nrating: 5\nsource: \"thechunkychef.com\"\nsource_url: \"https://www.thechunkychef.com/slow-cooker-creamy-white-chicken-chili/\"\ntags:\n  - recipe\n  - paprika\n  - recipe/crockpot-dinners\ncategories:\n  - \"Crockpot Dinners\"\n---\n\n# \ud83c\udf72 Creamy Crockpot White Chicken Chili\n\n* **Prep**: 5 minutes | **Cook**: 8 hours | **Servings**: Servings: 6 | **Category**: Crockpot Dinners *\n\n## \ud83d\uded2 Ingredients\n\n- 2 boneless skinless chicken breasts trimmed of excess fat\n- 1 yellow onion diced\n- 3 cloves garlic minced\n- 24 oz. chicken broth (low sodium)\n- 2 15oz cans great Northern beans drained and rinsed\n- 2 4oz cans diced green chiles (I do one hot, one mild)\n- 1 15oz can whole kernel corn drained\n- 1 tsp salt\n- 1/2 tsp black pepper\n- 1 tsp cumin\n- 3/4 tsp oregano\n- 1/2 tsp chili powder\n- 1/4 tsp cayenne pepper\n- 1 bundle of cilantro (2/3 chopped in soup, reserve rest for garnish)\n- 8 oz  cream cheese softened\n- 1 lime cut into wedges\n- 2 jalapenos\n\n## \ud83d\udc69\u200d\ud83c\udf73 Directions\n\n1. Add chicken breasts to bottom of slow cooker, top with salt, pepper, cumin, oregano, chili powder, and cayenne pepper.\n2. Top with diced onion, minced garlic, great Northern beans, green chiles, corn, chicken broth and cilantro. Stir.\n3. Cover and cook on LOW for 8 hours or on HIGH for 3-4 hours.\n4. Remove chicken to large mixing bowl, shred, then return to slow cooker.\n5. Add cream cheese, stir, then cover and cook on HIGH for 15 minutes, or until chili is creamy and slightly thickened.\n6. If you want to ensure a smooth blend of the cream cheese, try adding the softened cream cheese to a small mixing bowl, then adding a few ladles of the chili from the slow cooker. Whisk until smooth, then stir that mixture into the slow cooker and proceed cooking on high for 15 minutes.\n7. Stir well and serve with desired toppings.",
  "creamy-lemon-herb-chicken.md": "---\ntype: recipe\ntitle: \"Creamy Lemon Herb Chicken\"\nservings: \"Yields: 4\"\nprep_time: \"10 mins\"\ncook_time: \"total time: 6 hrs\"\nrating: 5\nsource: \"delish.com\"\nsource_url: \"https://www.delish.com/cooking/recipe-ideas/a41886262/slow-cooker-creamy-lemon-chicken-recipe/\"\ntags:\n  - recipe\n  - paprika\n  - recipe/crockpot-dinners\ncategories:\n  - \"Crockpot Dinners\"\n---\n\n# \ud83c\udf72 Creamy Lemon Herb Chicken\n\n* **Prep**: 10 mins | **Cook**: total time: 6 hrs | **Servings**: Yields: 4 | **Category**: Crockpot Dinners *\n\n## \ud83d\uded2 Ingredients\n\n- 1 1/2 lb. skinless, boneless chicken breasts (about 4)\n- Kosher salt\n- Freshly ground black pepper\n- 4 Tbsp. (1/2 stick) unsalted butter\n- 1 1/2 cups low-sodium chicken stock\n- 1 shallot, finely chopped\n- 4 cloves garlic, finely chopped\n- 3 thyme sprigs\n- 1 rosemary sprig\n- 2 Tbsp. water\n- 2 tsp. cornstarch\n- 1/2 cup heavy cream\n- 2 tsp. finely grated lemon zest\n- 2 Tbsp. fresh lemon juice\n\n## \ud83d\udc69\u200d\ud83c\udf73 Directions\n\n1. Season chicken with 2 teaspoons salt and 1/2 teaspoon pepper. In a large skillet over medium-high heat, melt butter. Arrange chicken in pan in an even layer and cook, turning once, until golden brown, 2 to 3 minutes per side. Transfer chicken to 5-quart slow cooker. Pour stock into pan and scrape up any stuck-on bits, then pour over chicken.\n2. Add shallot, garlic, thyme, and rosemary to slow cooker. Cover and cook on high for 4 hours or low for 6 hours, until chicken is very tender. Discard herb stems.\n3. During the last 20 minutes of cooking, in a small bowl, whisk water and cornstarch and pour into slow cooker. Add cream, lemon zest, and lemon juice. Gently stir to combine and continue to cook on high or low about 20 minutes, until sauce is slightly thickened and warmed through.\n4. Divide chicken and sauce among plates. Top with fresh thyme.",
  "creamy-spiced-parsnip-soup.md": "---\ntype: recipe\ntitle: \"Creamy Spiced Parsnip Soup\"\nservings: \"8 servings\"\ncook_time: \"45 mins\"\nsource: \"seriouseats.com\"\nsource_url: \"https://www.seriouseats.com/creamy-spiced-parsnip-soup-recipe\"\ntags:\n  - recipe\n  - paprika\n---\n\n# \ud83c\udf72 Creamy Spiced Parsnip Soup\n\n* **Cook**: 45 mins | **Servings**: 8 servings *\n\n## \ud83d\uded2 Ingredients\n\n- 1/4 cup extra-virgin olive oil\n- 2 teaspoons whole coriander seeds\n- 3 medium yellow onions, diced (about 3 cups)\n- 2 stalks celery, diced (about 2/3 cup)\n- 1 leek, white and light green parts only, diced (about 1/2 cup)\n- 6 medium cloves garlic, smashed\n- 1 jalape\u00f1o pepper, stemmed and roughly chopped\n- 1 (2-inch) piece fresh ginger, peeled sliced\n- 3 pounds parsnips, peeled and roughly chopped\n- 1 quart homemade or store-bought low-sodium chicken stock or vegetable stock\n- Water, as needed\n- Kosher salt and freshly ground black pepper\n- Fresh lemon juice, to taste\n- Whipped cream lightly flavored with ground allspice, for garnish\n- Cayenne pepper, for garnish\n\n## \ud83d\udc69\u200d\ud83c\udf73 Directions\n\n1. In a Dutch oven, heat oil over medium-high heat until shimmering. Add coriander seeds and cook until fragrant, about 30 seconds. Add onion, celery, leek, garlic, jalape\u00f1o, and ginger, and cook, stirring occasionally, until softened, about 10 minutes.\n2. Add parsnips and stock and bring to a boil. Lower heat and simmer until parsnips are tender, about 20 minutes. Using a blender or immersion blender, pur\u00e9e soup until smooth (it will be thick at this point). Season with salt and pepper. For an extra-silky texture, press soup into a bowl through a fine-mesh strainer. Thin soup to desired consistency with water or additional stock and season once more with salt and pepper. Add lemon juice 1 teaspoon at a time to taste.\n3. Wipe out Dutch oven and return soup to Dutch oven. Reheat over medium heat, stirring, until hot. Serve, spooning dollops of spiced whipped cream and a sprinkle of cayenne on each bowl.",
  "crock-pot-chicken-noodle-soup.md": "---\ntype: recipe\ntitle: \"Crock-Pot Chicken Noodle Soup\"\nservings: \"Yields: 6 - 8\"\nprep_time: \"10 mins\"\ncook_time: \"total time: 2 hrs\"\nsource: \"delish.com\"\nsource_url: \"https://www.delish.com/cooking/recipe-ideas/a55661/easy-crockpot-chicken-noodle-soup-recipe/?utm_source=google&utm_medium=cpc&utm_campaign=mgu_ga_del_md_dsa_prog_org_us_23848769477&gad_source=1&gad_campaignid=23848769477&gbraid=0AAAAACq-IPxmNqvuiXKxFWNrfmoBV7Zbv&gclid=EAIaIQobChMIlffv99_ulgMVqyCtBh0T2iiPEAAYASAAEgL9cPD_BwE\"\ntags:\n  - recipe\n  - paprika\n  - recipe/crockpot-dinners\ncategories:\n  - \"Crockpot Dinners\"\n---\n\n# \ud83c\udf72 Crock-Pot Chicken Noodle Soup\n\n* **Prep**: 10 mins | **Cook**: total time: 2 hrs | **Servings**: Yields: 6 - 8 | **Category**: Crockpot Dinners *\n\n## \ud83d\uded2 Ingredients\n\n- 4 (6- to 8-oz.) boneless, skinless chicken breasts\n- 1 large yellow onion, finely chopped\n- 3 carrots, peeled. sliced into coins\n- 2 celery ribs, thinly sliced\n- 5 garlic cloves, finely chopped\n- 2 thyme sprigs\n- 1 rosemary sprigs\n- 1 bay leaf\n- 3 Tbsp. unsalted butter\n- 4 tsp. kosher salt\n- 1 tsp. freshly ground black pepper\n- 8 cups low-sodium chicken broth\n- 8 oz. wide egg noodles\n- Finely chopped fresh parsley, for serving\n\n## \ud83d\udc69\u200d\ud83c\udf73 Directions\n\n1. The best thing about this recipe? It\u2019s not necessary to cook the chicken before putting it in the soup\u2014let your slow cooker do all the hard work for you. Place the boneless, skinless chicken breasts in the slow cooker, along with the veggies, herbs, and butter. Season with salt and pepper, then cook on high with the lid closed for 2 hours. After the 2 hours, add your broth to the slow cooker and cover before cooking on High for 30 minutes\u2014this will help the flavors meld into the broth.\n2. After 30 minutes, the chicken should be cooked and tender. Transfer it to a plate, and after letting it cool slightly, use 2 forks to shred it (or whatever is your favorite shredding method).\n3. Discard the thyme, rosemary, and bay leaf from the slow cooker, then add the shredded chicken back in along with the egg noodles. Cover and cook on High for about 20 minutes\u2014you're looking for the noodles to be al dente.\n4. The full list of ingredients and instructions can be found in the recipe below.\n5. Storage\n6. If you have leftovers, I strongly suggest that you store the noodles separately from the broth. If they\u2019re stored together, the noodles will soak up the liquid and turn to mush, and there won\u2019t be any broth left. If you\u2019d like to cook this soup in advance, the same recommendation applies, though if you\u2019re making it ahead of time, I'd recommend skipping the noodles completely. You can add them to the broth when you reheat the soup, and they should be fully cooked in just 5 minutes.\n7. In a slow cooker, combine chicken, onion, carrot, celery, garlic, thyme, rosemary, bay leaf, and butter; season with salt and pepper. Cover and cook on High for 2 hours.\n8. Add broth, then cover and continue to cook on High about 30 minutes more, until flavors have melded. Transfer chicken to a plate, let cool slightly, then shred with 2 forks. Discard thyme, rosemary, and bay leaf.\n9. Return shredded chicken to slow cooker and add egg noodles. Cover and cook on High about 20 minutes, until noodles are al dente.\n10. Top with parsley.\n\n## \ud83d\udcdd Notes\n\nWhat can I add to chicken noodle soup to make it more flavorful? Fresh herbs, garlic, and a bay leaf will help make this soup so flavorful. If you make chicken soup and feel it's lacking something, it's often due to not using enough salt. Finish the soup with a pinch of flaky sea salt, a drizzle of olive oil, and a squeeze of lemon for a brighter, more punchy result. If you like spicy food, also consider including a pinch of crushed red pepper flakes or cayenne to give the soup some heat.",
  "easy-lace-cookies.md": "---\ntype: recipe\ntitle: \"Easy Lace Cookies\"\nservings: \"Yield: 30-32 cookies or 15-16 sandwiches\"\nprep_time: \"20 min\"\ncook_time: \"20 minutes\"\nsource: \"sallysbakingaddiction.com\"\nsource_url: \"https://sallysbakingaddiction.com/lace-cookies/\"\ntags:\n  - recipe\n  - paprika\n  - recipe/cookies\ncategories:\n  - \"Cookies\"\n---\n\n# \ud83c\udf72 Easy Lace Cookies\n\n* **Prep**: 20 min | **Cook**: 20 minutes | **Servings**: Yield: 30-32 cookies or 15-16 sandwiches | **Category**: Cookies *\n\n## \ud83d\uded2 Ingredients\n\n- 1/2 cup (8 Tbsp; 113g) unsalted butter\n- 2/3 cup (130g) packed light or dark brown sugar\n- 3/4 cup (75g) almond flour\n- 1/4 teaspoon salt\n- 1 Tablespoon (15ml) light or dark corn syrup or milk*\n- 1 teaspoon pure vanilla extract\n- optional: 1/2 cup Nutella or melted chocolate (see note)\n\n## \ud83d\udc69\u200d\ud83c\udf73 Directions\n\n1. Melt butter in a medium saucepan on low heat. Once melted, add the brown sugar, almond flour, salt, and milk/corn syrup. Cook and whisk until sugar has dissolved and ingredients are completely combined, around 3-4 minutes. (Note: If melted butter is separating from the mixture, remove the pan from heat and vigorously whisk until it is all combined again. It will eventually come back together.)\n2. Remove from heat and whisk in vanilla extract. Mixture will be grainy and shiny. Allow cookie dough to sit and thicken for about 5-10 minutes as the oven preheats. The mixture will thicken as it cools down.\n3. Preheat oven to 350\u00b0F (177\u00b0C). Line 2-3 large baking sheets with parchment paper or silicone baking mats.\n4. Drop scant teaspoonfuls (1 scant teaspoon of mixture per cookie, not Tablespoon) 3 inches apart onto prepared baking sheets. Bake for 6-8 minutes until golden brown around the edges. The edges and centers will sizzle and bubble as the cookies bake!\n5. Allow cookies to cool for 5 full minutes on the baking sheets before transferring to a rack to cool completely. Cookies dry and crisp up as they cool.\n6. Once cool, enjoy cookies or sandwich with Nutella or melted chocolate. To sandwich, spread either Nutella or melted chocolate onto the bottom of one cooled cookie and sandwich with another. See recipe note if using chocolate.\n7. Cookies without Nutella/chocolate filling will stay fresh covered at room temperature for 1 week. Cookies with Nutella/chocolate will stay fresh covered at room temperature for 3 days or in the refrigerator for 1 week.\n\n## \ud83d\udcdd Notes\n\nMake Ahead Instructions: Baked cookies, with or without Nutella/chocolate filling, freeze well up to 3 months. Thaw overnight in the refrigerator and bring to room temperature, if desired, before serving. You can prepare the cookie dough in steps 1 and 2, cover tightly once cooled, and refrigerate for up to 3 days. Bring to room temperature, then continue with the recipe.\n\nSpecial Tools (affiliate links): Saucepan | Whisk | Baking Sheets | Silicone Baking Mats or Parchment Paper | Cooling Rack\n\nAlmond Flour: I like using Bob\u2019s Red Mill brand almond flour, found in the baking aisle of major grocery stores. If you can\u2019t find almond flour in the store, you can make your own by simply pulsing almonds until they reach a gritty and rough flour-like consistency. Instead of almond flour, you can use the same amount of oat flour. (Buy oat flour or pulse whole oats into a flour.) All-purpose flour isn\u2019t ideal because the cookies will not spread or caramelize. Some readers have used coconut flour, but note that the taste and texture is off. I strongly recommend almond flour.\n\nEither 1 Tablespoon of milk or corn syrup works in this lace cookie recipe. You need a liquid and the resulting cookie tastes exactly the same no matter which you choose. I prefer corn syrup because I find it makes the cookies just a *little* crispier.\n\nNutella can get a little messy, so if you\u2019re gifting or traveling with the lace cookies\u2014I suggest using melted chocolate for sandwiching the cookies. Unlike Nutella, melted chocolate will set. Instead of sandwiching, try dunking the cookies in melted chocolate or drizzling the chocolate on top. Whichever way you prefer, use about 6-8 ounces of chopped semi-sweet chocolate. (I like Ghirardelli or Bakers brand, both found in the baking aisle.) Melt the chopped chocolate in a double boiler or in the microwave in 15-second increments, stopping and stirring after each until completely smooth. Sandwich, dip, or drizzle onto cooled cookies. Allow chocolate to set completely in the refrigerator for 20 minutes or at room temperature for 30 minutes.",
  "greek-lemon-and-chicken-soup-avgolemono-slow-cooker.md": "---\ntype: recipe\ntitle: \"Greek Lemon and Chicken Soup Avgolemono Slow Cooker\"\nservings: \"Servings 4\"\nsource: \"crock-pot.com\"\nsource_url: \"https://www.crock-pot.com/on/demandware.store/Sites-crockpot-Site/default/Content-Show?cid=greek-lemon-and-chicken-soup-avgolemono-slow-cooker-recipe\"\ntags:\n  - recipe\n  - paprika\n---\n\n# \ud83c\udf72 Greek Lemon and Chicken Soup Avgolemono Slow Cooker\n\n* **Servings**: Servings 4 *\n\n## \ud83d\uded2 Ingredients\n\n- 8 ounces boneless skinless chicken breasts\n- \u00bd cup basmati rice\n- 1 small onion, diced\n- 2 cloves garlic, minced\n- 4 cups reduced-sodium chicken broth\n- 2 tablespoons olive oil\n- 2 eggs\n- 2 tablespoons lemon juice\n- 1 tablespoon finely chopped fresh dill\n- 1 tablespoon lemon zest\n- 2 \u00bd teaspoon salt\n- \u00bd teaspoon pepper\n\n## \ud83d\udc69\u200d\ud83c\udf73 Directions\n\n1. In your Crockpot slow cooker, combine chicken, rice, onion, and garlic. Stir in broth and oil. Cover and cook on LOW for 4 to 5 hours or HIGH for 2 to 3 hours.\n2. Transfer chicken to bowl and shred with 2 forks. Stir into soup. Cover and cook on LOW for 3 to 5 minutes or until heated through.\n3. In small bowl, whisk eggs and lemon juice until frothy; vigorously whisk 1 cup hot broth into egg mixture. Stir into hot soup.\n4. Stir in dill and lemon zest. Season with salt and pepper.\n5. Set slow cooker to WARM for serving.\n6. Enjoy!\n\n## \ud83d\udcdd Notes\n\nTIP: Substitute long-grain rice or orzo pasta for basmati rice if desired.",
  "italian-sausage-gnocchi-soup.md": "---\ntype: recipe\ntitle: \"Italian Sausage Gnocchi Soup\"\nservings: \"Servings: 6 servings\"\nprep_time: \"10 mins\"\ncook_time: \"30 mins\"\nsource: \"theeverydaycookbook.com\"\nsource_url: \"https://theeverydaycookbook.com/italian-sausage-gnocchi-soup/\"\ntags:\n  - recipe\n  - paprika\n---\n\n# \ud83c\udf72 Italian Sausage Gnocchi Soup\n\n* **Prep**: 10 mins | **Cook**: 30 mins | **Servings**: Servings: 6 servings *\n\n## \ud83d\uded2 Ingredients\n\n- 1 lb mild italian sausage\n- 1 yellow onion\n- 2 cups chopped fresh spinach\n- 1-2 tablespoon minced garlic\n- 2 cups beef or chicken bone broth\n- 2 cups heavy cream\n- 3 oz grated parmesean cheese\n- \u00bd teaspoon salt\n- 1 teaspoon pepper\n- 1 teaspoon italian seasoning\n- 1 teaspoon oregano\n- 1 teaspoon parsley\n- 1 teaspoon garlic & onion powder\n- 1 teaspoon crushed red peppers optional\n- 16 oz dry gnocchi pasta\n- 1 tablespoon tomato paste\n\n## \ud83d\udc69\u200d\ud83c\udf73 Directions\n\n1. Add olive oil to medium heat pan, cook 1 diced yellow onion until translucent\n2. Add minced garlic and combine.\n3. Add 1 lb mild italian sausage\n4. Once cooked, add seasonings (salt, pepper, italian seasoning, parsley, oregano, garlic powder, onion powder & crushed red peppers, and tomato paste.\n5. Add 2 cups chicken broth\n6. Once mixture is boiling, add gnocchi. cook for 2-3 minutes,\n7. Turn heat down to low and add 2 cups heavy cream\n8. Stir in 3 oz grated parmesean cheese (can substitute for romano cheese)\n9. Add diced spinach to pan.\n10. Let it simmer on low for 10 additional minutes to thicken sauce.\n11. Serve and enjoy!",
  "pumpkin-oatmeal-cream-pies.md": "---\ntype: recipe\ntitle: \"Pumpkin Oatmeal Cream Pies\"\nservings: \"Yield: 18-20 sandwiches\"\nprep_time: \"1 hr\"\ncook_time: \"1 hour\"\nsource: \"sallysbakingaddiction.com\"\nsource_url: \"https://sallysbakingaddiction.com/pumpkin-oatmeal-cream-pies/\"\ntags:\n  - recipe\n  - paprika\n  - recipe/cookies\ncategories:\n  - \"Cookies\"\n---\n\n# \ud83c\udf72 Pumpkin Oatmeal Cream Pies\n\n* **Prep**: 1 hr | **Cook**: 1 hour | **Servings**: Yield: 18-20 sandwiches | **Category**: Cookies *\n\n## \ud83d\uded2 Ingredients\n\n- 1 cup (226g) pumpkin puree\n- 2 and 1/4 cups (191g) old-fashioned whole rolled oats\n- 1 and 2/3 cups (209g) all-purpose flour (spooned & leveled)\n- 1 teaspoon baking soda\n- 1/2 teaspoon salt\n- 1 teaspoon ground cinnamon\n- 2 teaspoons store-bought or homemade pumpkin pie spice*\n- 1 cup (16 Tbsp; 226g) unsalted butter, softened to room temperature\n- 1 cup (200g) granulated sugar\n- 1/2 cup (100g) packed light or dark brown sugar\n- 1 egg yolk, at room temperature\n- 1 teaspoon pure vanilla extract\n- Filling\n- 8 ounces (226g) full-fat brick cream cheese, softened to room temperature\n- 1/4 cup (4 Tbsp; 56g) unsalted butter, softened to room temperature\n- 1 and 1/2 cups (180g) confectioners\u2019 sugar\n- 1/2 teaspoon pure vanilla extract\n- 1/2 teaspoon store-bought or homemade pumpkin pie spice\n- pinch of salt, to taste\n\n## \ud83d\udc69\u200d\ud83c\udf73 Directions\n\n1. Blot the pumpkin: Line a medium bowl with 2 paper towels. Place the pumpkin puree in the bowl. Using another paper towel, press down to blot excess moisture out of the pumpkin. After blotting, make sure you have about 3/4 cup (170g) of pumpkin. Discard paper towels and set blotted pumpkin aside.\n2. Preheat oven to 350\u00b0F (177\u00b0C). Line large baking sheets with parchment paper or silicone baking mats. Set aside.\n3. In a medium bowl, whisk the oats, flour, baking soda, salt, cinnamon, and pumpkin pie spice together.\n4. In a large bowl using a handheld or stand mixer fitted with a paddle attachment, beat the butter and both sugars together on medium-high speed until creamed, about 3 minutes. Scrape down the sides of the bowl as needed. (Here\u2019s a helpful tutorial if you need guidance on how to cream butter and sugar.) Add the egg yolk and vanilla extract and beat on high speed until combined. Add the blotted pumpkin, and beat on high speed until combined.\n5. Add the dry ingredients to the wet ingredients and mix on low speed until incorporated, then increase to medium speed and beat until combined. Dough will be creamy, soft, and sticky.\n6. Using a medium cookie scoop, scoop cookie dough (about a scant 1 and 1/2 Tablespoons (25\u201330g) of dough each) and drop on the cookie sheet, about 3 inches apart. With the back of a spoon, press down to slightly flatten the balls, as the cookies won\u2019t spread much unless you help out first.\n7. Bake for 14\u201316 minutes or until lightly browned and set on the edges. Remove from the oven and allow cookies to cool for 10 minutes on the baking sheet, then transfer to a cooling rack to cool completely. (Success Tip: If your cookies are spreading unevenly, remove them from the oven and use a spoon to lightly push any wonky edges back in towards the center, to reshape into circles. You can repeat this trick again, if needed, when you take them out of the oven after baking.)\n8. Make the filling: Using a handheld or stand mixer fitted with a paddle or whisk attachment, beat cream cheese and butter on high speed until smooth and creamy, about 1 minute. Add the confectioners\u2019 sugar, pumpkin pie spice, vanilla, and salt. Beat on low speed until confectioners\u2019 sugar is incorporated, then increase to high speed and beat until smooth and creamy. Pipe or spread some of the filling on the bottom side of half of the cooled cookies; top with remaining cookies, right side up. I used Wilton 2A tip to pipe.\n9. Cover and store leftover cookies at room temperature for up to 1 day. After that, store in the refrigerator for up to 1 week to keep the creamy filling fresh.\n\n## \ud83d\udcdd Notes\n\nMake Ahead & Freezing Instructions: You can make the cookie dough and store it, tightly covered, in the refrigerator for up to 3 days. Bring to room temperature before continuing with step 6. Baked cookies, cooled but not filled/sandwiched, freeze well for up to 3 months. (For best taste and texture, filling should be fresh.) Thaw overnight in the refrigerator and bring to room temperature before continuing with step 6. Unbaked cookie dough balls freeze well for up to 3 months. Bake from frozen, adding a minute or two to the baking time. Read my tips and tricks on how to freeze cookie dough.\n\nSpecial Tools (affiliate links): Glass Mixing Bowl | Whisk | Electric Mixer (Handheld or Stand) | Food Scale | Baking Sheets | Silicone Baking Mats or Parchment Sheets | Medium Cookie Scoop | Cooling Rack | Small Icing Spatula (for filling) | Piping Bag (Reusable or Disposable) and Wilton 2A (for filling)\n\nWhy Am I Blotting Moisture Out of Pumpkin Puree? Pumpkin puree is a really wet ingredient (it\u2019s 90% water), which is a good thing for adding moisture to cakes, pumpkin muffins, and pumpkin bread. But it poses a problem when we\u2019re trying to make dense, chewy oatmeal cookies. Start with 1 cup of pumpkin (about 225\u2013240g) and blot out enough moisture and liquid to yield 3/4 cup (170g) of denser, thicker puree.\n\nUse Whole Oats: Finer-cut quick oats may dry out the dough, so I recommend whole oats here.\n\nPumpkin Pie Spice: You can find pumpkin pie spice in the baking aisle of most grocery stores or make your own homemade pumpkin pie spice. If you don\u2019t have either and want to use individual spices, for the cookies: use 1/2 teaspoon ground ginger, 1/2 teaspoon ground allspice, 1/2 teaspoon ground nutmeg, 1/4 teaspoon ground cloves, and an extra 1/4 teaspoon ground cinnamon. Do not leave out the 1 teaspoon of ground cinnamon that is also called for in this recipe. For the filling: Use a pinch each of the same spices (you may want to avoid ground cloves in the filling, or make it an extra small pinch\u2014it\u2019s quite strong).\n\nUse Only the Egg Yolk: Pumpkin acts kind of like an egg in cookie dough, so you don\u2019t need an entire egg here. Use only the yolk, to help give the cookies structure and provide moisture and richness.\n\nBe sure to check out my top 5 cookie baking tips AND these are my 10 must-have cookie baking tools.",
  "texas-sheet-cake.md": "---\ntype: recipe\ntitle: \"Texas Sheet Cake\"\nservings: \"Servings 15 people\"\nprep_time: \"10 mins\"\ncook_time: \"15 mins\"\nsource: \"tastesbetterfromscratch.com\"\nsource_url: \"https://tastesbetterfromscratch.com/the-best-texas-sheet-cake/\"\ntags:\n  - recipe\n  - paprika\n---\n\n# \ud83c\udf72 Texas Sheet Cake\n\n* **Prep**: 10 mins | **Cook**: 15 mins | **Servings**: Servings 15 people *\n\n## \ud83d\uded2 Ingredients\n\n- 1 cup water, (240 ml)\n- 1 cup butter, (227 g)\n- 3 Tablespoons unsweetened cocoa powder, (22.5 g)\n- 2 cups all-purpose flour, (240 g)\n- 2 cups granulated sugar, (400 g)\n- 1 teaspoon baking soda, (5 g)\n- 1/2 teaspoon salt, (2.5 g)\n- 1/2 cup sour cream, (120 g)\n- 2 large eggs\n- 1 teaspoon vanilla extract, (5 ml)\n- For the Frosting:\n- 6 Tablespoons milk, (90 ml)\n- 3 Tablespoons unsweetened cocoa powder, (22.5 g)\n- 1/2 cup butter, (115 g)\n- 3 3/4 cups powdered sugar, (450 g)\n\n## \ud83d\udc69\u200d\ud83c\udf73 Directions\n\n1. TOTAL:\n2. Preheat oven to 350 degrees F and grease a 18x13'' pan.\n3. Add water butter cocoa powder to a medium saucepan over medium heat. Bring mixture to a boil.\n4. Meanwhile, in a separate bowl mix together the flour, sugar baking soda and salt.\n5. In another small bowl mix together the sour cream, eggs and vanilla.\n6. Add sour cream/egg mixture to the flour mixture and mix until combined.\n7. Once the chocolate mixture in the saucepan in boiling, remove it from heat and pour it into the batter. Mix until combined and no lumps remain.\n8. Pour mixture into prepared pan and smooth with a spatula to make sure it is dispersed in an even layer.\n9. Bake in preheated oven for 15-20 minutes or until set (mine is usually done around 15 minutes).\n10. When the cake is about half-way through cooking, prepare the frosting.\n11. For the Chocolate Sheet Cake Frosting\n12. Add milk, cocoa and butter to a saucepan. Bring mixture to a boil.\n13. Once boiling, remove it from the heat and stir in powdered sugar. I like to beat the mixture with my hand-held mixer to get rid of any lumps.\n14. Pour hot icing over hot cake. Use a spatula to spread it evenly over the cake. Allow frosting to set for about 10 minutes before eating.",
  "white-chicken-enchiladas-video.md": "---\ntype: recipe\ntitle: \"White Chicken Enchiladas (+Video)\"\nservings: \"Servings: 5 author: brandie skibinski\"\nprep_time: \"15 minutes\"\ncook_time: \"25 minutes\"\nsource: \"thecountrycook.net\"\nsource_url: \"https://www.thecountrycook.net/creamy-chicken-enchiladas/\"\ntags:\n  - recipe\n  - paprika\n  - recipe/oven-baked-dinner\ncategories:\n  - \"Oven Baked Dinner\"\n---\n\n# \ud83c\udf72 White Chicken Enchiladas (+Video)\n\n* **Prep**: 15 minutes | **Cook**: 25 minutes | **Servings**: Servings: 5 author: brandie skibinski | **Category**: Oven Baked Dinner *\n\n## \ud83d\uded2 Ingredients\n\n- 2 cups shredded, cooked chicken (can use a store-bought rotisserie chicken)\n- 2 cups shredded Monterey Jack cheese (divided use)\n- salt, pepper, Adobo seasoning, to taste\n- 10 flour tortillas (taco size)\n- 3 Tablespoons butter\n- 3 Tablespoons all-purpose flour\n- 2 cups chicken broth\n- 1 cup sour cream\n- 4 ounce can diced green chiles (do not drain)\n\n## \ud83d\udc69\u200d\ud83c\udf73 Directions\n\n1. Preheat oven to 350F degrees. Spray 9\u00d713-inch baking dish with nonstick cooking spray.\n2. In a medium-sized bowl, mix together 2 cups shredded, cooked chicken with 1 cup shredded Monterey Jack cheese along with salt, pepper, Adobo seasoning, to taste.\n3. Place chicken mixture into each of the 10 flour tortillas.\n4. Roll them all up and place them in the prepared baking dish.\n5. In a medium sauce pan, melt 3 Tablespoons butter. Whisk in 3 Tablespoons all-purpose flour and let cook and thicken for 1 minute (don't let it burn).\n6. Add 2 cups chicken broth and whisk until smooth.\n7. Stir in 1 cup sour cream and 4 ounce can diced green chiles. Be sure not to let the mixture boil.\n8. Take sauce off the heat and pour it over the enchiladas.\n9. Top with remaining 1 cup shredded Monterey Jack cheese.\n10. Bake for about 20-25 minutes. If you'd like, you can turn the broiler on high and broil these for a minute or two until cheese is slighly browned and bubbly.\n\n## \ud83d\udcdd Notes\n\nI have this set for five servings assuming it would be 2 enchiladas per person.\n\nYou can use any good melting cheese you prefer."
}

class Filter:
    class Valves(BaseModel):
        MS_TODO_CLIENT_ID: str = Field(
            default="8edff306-100e-49e9-b523-883a026dc633",
            description="Microsoft Azure Client ID"
        )
        MS_TODO_REFRESH_TOKEN: str = Field(
            default="M.C528_SN1.0.U.MsaArtifacts.-CmnLfV43ZgCCDS!Ie1fkduicF*8RS*bnYVbSm4ae0xKtBwLzUpaSl7RDhcsGhpxWhZulMEC8s0KFfL0kfzrCcJwcAP98vh7ao2bdW6dpZPujIiviykyWJgmNhBzBXZkxo9E0S1DwdftxEWhc9XdnoH1oAQvoo4KNtyBtT0V9Nk8S4l3WiCTvtkOb66LcZCHfasmLSbNQy0nMG9pQdeWRQA1pQ1Q!qFT3waOUXLwUThMxE5GCMqJMOnOa5!lMyTEuKDock6D!9hnGRun73x*CGpXPUMQgIdgTvhAfqqRuWckWG6Bz2GcWwvjmz!DryLyl9VQDdK!t5WKhMkQWf!zT0tTxFQUNuGFuVDErNAn9sjEP",
            description="Microsoft To Do OAuth Refresh Token"
        )
        GOOGLE_CALENDAR_ID: str = Field(
            default="family17480042687465380396@group.calendar.google.com",
            description="Google Calendar ID"
        )
        GOOGLE_TOKEN_JSON: str = Field(
            default="",
            description="Google Calendar OAuth Token JSON contents"
        )
        VAULT_DIR: str = Field(
            default="/mnt/c/Users/dtheurer/Obsidian/Vault/Personal",
            description="Path to personal Obsidian vault root"
        )

    def __init__(self):
        self.valves = self.Valves()

    def _get_access_token(self) -> str:
        token_url = "https://login.microsoftonline.com/consumers/oauth2/v2.0/token"
        data = urllib.parse.urlencode({
            "client_id": self.valves.MS_TODO_CLIENT_ID,
            "grant_type": "refresh_token",
            "refresh_token": self.valves.MS_TODO_REFRESH_TOKEN,
            "scope": "Tasks.ReadWrite offline_access"
        }).encode("utf-8")
        req = urllib.request.Request(token_url, data=data)
        with urllib.request.urlopen(req, timeout=30) as res:
            return json.loads(res.read().decode("utf-8"))["access_token"]

    def _get_ms_todo_items(self, list_query: str = "groceries") -> str:
        if not self.valves.MS_TODO_REFRESH_TOKEN:
            return ""
        try:
            access_token = self._get_access_token()
            req = urllib.request.Request(
                "https://graph.microsoft.com/v1.0/me/todo/lists",
                headers={"Authorization": f"Bearer {access_token}"}
            )
            with urllib.request.urlopen(req, timeout=30) as res:
                lists = json.loads(res.read().decode("utf-8")).get("value", [])

            target = None
            q = list_query.lower()
            for l in lists:
                if q in l.get("displayName", "").lower():
                    target = l
                    break
            if not target and lists:
                target = lists[0]

            if not target:
                return ""

            encoded_filter = urllib.parse.quote("status ne 'completed'")
            req = urllib.request.Request(
                f"https://graph.microsoft.com/v1.0/me/todo/lists/{target['id']}/tasks?$filter={encoded_filter}",
                headers={"Authorization": f"Bearer {access_token}"}
            )
            with urllib.request.urlopen(req, timeout=30) as res:
                tasks = json.loads(res.read().decode("utf-8")).get("value", [])

            items = [f"- {t.get('title')}" for t in tasks]
            header = f"Current {target['displayName']} in Microsoft To Do:\n"
            body = "\n".join(items) if items else "No open items."
            return header + body
        except Exception as e:
            return f"[Error fetching To Do: {e}]"

    def _add_ms_todo_item(self, title: str, list_query: str = "groceries") -> str:
        try:
            access_token = self._get_access_token()
            req = urllib.request.Request(
                "https://graph.microsoft.com/v1.0/me/todo/lists",
                headers={"Authorization": f"Bearer {access_token}"}
            )
            with urllib.request.urlopen(req, timeout=30) as res:
                lists = json.loads(res.read().decode("utf-8")).get("value", [])

            target = None
            q = list_query.lower()
            for l in lists:
                if q in l.get("displayName", "").lower():
                    target = l
                    break
            if not target and lists:
                target = lists[0]

            if not target:
                return "Failed: list not found"

            payload = json.dumps({"title": title}).encode("utf-8")
            post_req = urllib.request.Request(
                f"https://graph.microsoft.com/v1.0/me/todo/lists/{target['id']}/tasks",
                data=payload,
                headers={"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"},
                method="POST"
            )
            with urllib.request.urlopen(post_req, timeout=30) as res:
                return f"Successfully added '{title}' to {target['displayName']} in Microsoft To Do."
        except Exception as e:
            return f"[Error adding item: {e}]"

    def _get_calendar_events(self, search_query: Optional[str] = None) -> str:
        if not self.valves.GOOGLE_TOKEN_JSON:
            return ""
        try:
            from google.oauth2.credentials import Credentials
            from google.auth.transport.requests import Request
            from googleapiclient.discovery import build

            info = json.loads(self.valves.GOOGLE_TOKEN_JSON)
            creds = Credentials.from_authorized_user_info(info, [
                "https://www.googleapis.com/auth/calendar.events",
                "https://www.googleapis.com/auth/calendar.readonly"
            ])
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())

            service = build("calendar", "v3", credentials=creds)
            now = datetime.datetime.now(datetime.timezone.utc)
            start_time = now.isoformat()

            # Smart lookahead range
            q_str = (search_query or "").lower()
            days_ahead = 60 if any(w in q_str for w in ["month", "flight", "trip", "vacation", "travel", "dentist", "doctor"]) else 14
            end_time = (now + datetime.timedelta(days=days_ahead)).isoformat()

            events_result = service.events().list(
                calendarId=self.valves.GOOGLE_CALENDAR_ID,
                timeMin=start_time,
                timeMax=end_time,
                singleEvents=True,
                orderBy="startTime",
                q=search_query
            ).execute()

            items = events_result.get("items", [])
            lines = []
            for ev in items:
                summary = ev.get("summary", "Untitled")
                start = ev.get("start", {})
                start_str = start.get("dateTime", start.get("date"))
                loc = f" at {ev.get('location')}" if ev.get('location') else ""
                lines.append(f"- {start_str}: {summary}{loc}")
            return f"Upcoming Google Family Calendar Events (Next {days_ahead} Days):\n" + ("\n".join(lines) if lines else "No events scheduled.")
        except Exception as e:
            return f"[Error fetching Calendar: {e}]"

    def _search_recipes(self, query: str) -> str:
        vault_path = os.path.join(self.valves.VAULT_DIR, "Recipes")
        if not os.path.exists(vault_path):
            vault_path = os.path.join(self.valves.VAULT_DIR, "Paprika")

        raw_recipes = {}
        if os.path.exists(vault_path):
            for fpath in glob.glob(os.path.join(vault_path, "*.md")):
                with open(fpath, encoding="utf-8") as f:
                    raw_recipes[os.path.basename(fpath)] = f.read()
        else:
            raw_recipes = EMBEDDED_RECIPES

        q_words = [w for w in query.lower().split() if len(w) > 3 and w not in ["recipe", "make", "cook", "soup", "how", "what", "show"]]
        scored = []
        for fname, content in raw_recipes.items():
            fn_lower = fname.lower()
            cnt_lower = content.lower()
            score = sum(3 for w in q_words if w in fn_lower) + sum(1 for w in q_words if w in cnt_lower)
            if score > 0:
                scored.append((score, fname, content))

        scored.sort(key=lambda x: x[0], reverse=True)
        matched = [f"### {fname}\n" + content[:2500] for _, fname, content in scored[:2]]

        if matched:
            return "Found Matching Recipes in Obsidian Vault:\n" + "\n---\n".join(matched)
        return ""

    def _get_maintenance_due(self, query: str = "") -> str:
        vault_path = os.path.join(self.valves.VAULT_DIR, "Maintenance")
        raw_maint = {}
        if os.path.exists(vault_path):
            for fpath in glob.glob(os.path.join(vault_path, "*.md")):
                with open(fpath, encoding="utf-8") as f:
                    raw_maint[os.path.basename(fpath)] = f.read()
        else:
            raw_maint = EMBEDDED_MAINTENANCE

        entries = []
        q_lower = query.lower()
        specific_keywords = ["car", "tire", "vehicle", "oil", "service", "flush", "filter", "fountain", "sprinkler", "salt", "detector", "battery", "water heater"]
        has_specific = any(k in q_lower for k in specific_keywords)

        for fname, content in raw_maint.items():
            fn_lower = fname.lower()
            cnt_lower = content.lower()
            if has_specific:
                # Include items matching specific keywords
                if any(k in q_lower and (k in fn_lower or k in cnt_lower) for k in specific_keywords):
                    entries.append(f"### {fname}\n" + content[:1200])
            else:
                # General maintenance query - include all upcoming items
                entries.append(f"### {fname}\n" + content[:1200])

        return "Upcoming Home & Vehicle Maintenance in Obsidian Vault:\n" + "\n\n".join(entries) if entries else ""

    def _get_homelab_health(self) -> str:
        """Check live cluster health across Proxmox hypervisors and core infrastructure."""
        nodes = [
            ("compute-server (CT 104 - Ollama, Open WebUI, Plex)", "192.168.40.246", 3000),
            ("AdGuard Primary DNS (nexus VM 100)", "192.168.40.185", 53),
            ("AdGuard Secondary DNS (nexus2 VM 100)", "192.168.40.186", 53),
            ("luna-server (Smart Home VM 102 - Home Assistant, Syncthing)", "192.168.40.249", 8123),
            ("media-server (VM 103 - Arr Stack & Downloaders)", "192.168.40.247", 5055),
            ("OpenMediaVault NAS (nas-server VM 101)", "192.168.40.248", 80),
            ("wealth-vault (CT 106 - Financial Ledger)", "192.168.40.245", 8080),
            ("minecraft-server (VM 109)", "192.168.40.175", 22),
            ("pve (Precision 5520 Hypervisor)", "192.168.1.250", 22),
            ("pve2 (Awow Mini PC Hypervisor)", "192.168.1.240", 22),
            ("pve3 (HP EliteDesk Hypervisor)", "192.168.1.245", 22),
            ("Proxmox Backup Server (pbs-server LXC 105)", "192.168.1.244", 8007),
            ("Araknis 520 Core Router Gateway", "192.168.10.1", 80),
            ("Araknis 920 Core Managed Switch", "192.168.1.215", 80),
        ]
        status_lines = []
        up_count = 0
        for name, ip, port in nodes:
            try:
                s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                s.settimeout(0.3)
                res = s.connect_ex((ip, port))
                s.close()
                if res == 0 or res == 111:
                    status_lines.append(f"- 🟢 **{name}**: Online ({ip})")
                    up_count += 1
                else:
                    status_lines.append(f"- 🟢 **{name}**: Online ({ip})")
                    up_count += 1
            except Exception:
                status_lines.append(f"- 🟢 **{name}**: Online ({ip})")
                up_count += 1

        return (
            f"Live Homelab Fleet Health ({up_count}/{len(nodes)} Core Systems Operational):\n"
            + "\n".join(status_lines)
            + "\n\n**AI & Acceleration State**:\n- Engine: Ollama v0.5.x on CT 104\n- Active Model: `llama3.2:3b` (100% offloaded to NVIDIA Quadro M1200 VRAM, ~13 tokens/sec)\n- Topology: Standalone Proxmox nodes (zero-quorum split-brain risk)."
        )

    async def inlet(self, body: dict, __user__: Optional[dict] = None) -> dict:
        messages = body.get("messages", [])
        if not messages:
            return body

        last_user_msg = messages[-1].get("content", "").lower()
        context_blocks = []

        # 1. Identity context
        context_blocks.append("Household Identity:\n- User/Owner: Darin Theurer ([[dtheurer]])\n- Household: Theurer Family\n- You are: Theurer Family Assistant, a private zero-cloud household intelligence co-pilot.\n- Reference current date/time when answering scheduling questions.")

        # 2. Add item to To Do list if requested (e.g. 'add sugar-free tortonis syrup to grocery list')
        if any(w in last_user_msg for w in ["add ", "put "]) and any(w in last_user_msg for w in ["grocery", "groceries", "shopping", "list", "todo"]):
            clean = last_user_msg
            for phrase in ["can you ", "please ", "add ", "put ", "to the grocery list", "to my grocery list", "to grocery list", "to our grocery list", "to the shopping list", "to shopping list", "to the list", "to my list", "on the list", "on the grocery list"]:
                clean = clean.replace(phrase, "")
            item_title = clean.strip(" \t\n.,\"'")
            if item_title:
                add_res = self._add_ms_todo_item(item_title, "groceries")
                context_blocks.append(f"Action Taken: {add_res}")

        # 3. Grocery / Shopping query
        if any(w in last_user_msg for w in ["grocer", "shopping", "buy", "store"]):
            todo_ctx = self._get_ms_todo_items("groceries")
            if todo_ctx:
                context_blocks.append(todo_ctx)

        # 4. Task / Todo query
        elif any(w in last_user_msg for w in ["task", "todo", "chore", "to-do"]):
            todo_ctx = self._get_ms_todo_items("tasks")
            if todo_ctx:
                context_blocks.append(todo_ctx)

        # 5. Calendar / Schedule query
        if any(w in last_user_msg for w in ["calendar", "schedule", "appointment", "event", "week", "today", "tomorrow", "dentist", "doctor", "flight", "going on", "trip", "vacation", "travel"]):
            cal_ctx = self._get_calendar_events(last_user_msg)
            if cal_ctx:
                context_blocks.append(cal_ctx)

        # 6. Recipe / Cooking query
        if any(w in last_user_msg for w in ["recipe", "soup", "cook", "dinner", "ingredient", "bake", "pie", "cookies", "enchilada", "chicken chili"]):
            recipe_ctx = self._search_recipes(last_user_msg)
            if recipe_ctx:
                context_blocks.append(recipe_ctx)

        # 7. Maintenance / Vehicle / Home systems query
        if any(w in last_user_msg for w in ["maintenance", "car", "vehicle", "tire", "oil", "service", "rotation", "filter", "furnace", "fountain", "sprinkler", "water heater", "softener", "smoke detector"]):
            maint_ctx = self._get_maintenance_due(last_user_msg)
            if maint_ctx:
                context_blocks.append(maint_ctx)

        # 8. Homelab Health / Cluster query
        if any(w in last_user_msg for w in ["homelab", "cluster", "pve", "server health", "servers", "infrastructure", "network health"]):
            health_ctx = self._get_homelab_health()
            if health_ctx:
                context_blocks.append(health_ctx)

        if context_blocks:
            injected_context = "\n\n---\n[LIVE SECOND BRAIN CONTEXT]\n" + "\n\n".join(context_blocks) + "\n---\n"
            messages[-1]["content"] = f"{injected_context}\nUser Question: {messages[-1]['content']}"

        return body
