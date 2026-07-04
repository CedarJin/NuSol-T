"""SR Legacy data adapter — ingredient nutrient composition.

Supports three lookup strategies:
  1. Direct ndbNumber lookup (primary key for FNDDS ingredient mapping)
  2. FDC ID lookup
  3. Description-based search (exact, substring, word-overlap)
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from nusol.core.schema import NutrientProfile, NutrientRecord
from nusol.data.base import DataAdapterBase


class SRLegacyDataAdapter(DataAdapterBase):
    """Adapter for USDA SR Legacy database (ingredient nutrient profiles per 100g).

    Key features:
      - ndbNumber → nutrient profile (primary mapping from FNDDS)
      - fdcId → nutrient profile
      - Description search with multi-word overlap for handling cultivar/variety variants
      - Manual mapping table for edge cases
    """

    # Manual mapping for codes that cannot be resolved automatically
    MANUAL_NDB_MAP: dict[str, str] = {
        # Code -> ndbNumber
        "100260": "11457",   # Spinach, baby → Spinach, raw
        "100261": "11529",   # Tomato, roma → Tomatoes, red, ripe, raw
        "100299": "1267",    # Cheese, oaxaca, solid → Cheese, queso fresco
        "11966": "11935",    # Ketchup, restaurant → Catsup/Ketchup
    }

    def __init__(self, config: dict[str, Any] | None = None) -> None:
        super().__init__(config)
        self._data: dict[int, dict] = {}           # fdcId → food record
        self._profiles: dict[int, NutrientProfile] = {}  # fdcId → cached profile
        self._ndb_index: dict[str, int] = {}        # ndbNumber → fdcId
        self._name_index: dict[str, list[int]] = {} # lowercase name → [fdcIds]
        self._word_index: dict[str, set[int]] = {}  # word → {fdcIds}

    # ── Load ─────────────────────────────────────────────────────────────

    def load(self, path: str | Path) -> None:
        """Load SR Legacy JSON.

        Expected JSON structure: {"SRLegacyFoods": [{...}, ...]}
        """
        path = Path(path)
        with open(path, encoding="utf-8") as f:
            raw = json.load(f)

        foods = raw.get("SRLegacyFoods", [])
        self._data.clear()
        self._profiles.clear()
        self._ndb_index.clear()
        self._name_index.clear()
        self._word_index.clear()

        for food in foods:
            fdc_id = food.get("fdcId")
            if fdc_id is None:
                continue
            self._data[fdc_id] = food

            # Index by ndbNumber (primary key for FNDDS mapping)
            ndb = str(food.get("ndbNumber", ""))
            if ndb:
                self._ndb_index[ndb] = fdc_id

            # Index by name
            desc = food.get("description", "")
            name_lower = desc.lower().strip()
            if name_lower not in self._name_index:
                self._name_index[name_lower] = []
            self._name_index[name_lower].append(fdc_id)

            # Index by words (for multi-word overlap search)
            words = self._tokenize(name_lower)
            for word in words:
                if word not in self._word_index:
                    self._word_index[word] = set()
                self._word_index[word].add(fdc_id)

    # ── Lookup ───────────────────────────────────────────────────────────

    def get_by_ndb_number(self, ndb_number: str | int) -> NutrientProfile | None:
        """Get nutrient profile by USDA NDB number.

        This is the primary mapping path from FNDDS ingredientCode.
        """
        key = str(ndb_number)
        fdc_id = self._ndb_index.get(key)
        if fdc_id is None:
            # Check manual map
            mapped = self.MANUAL_NDB_MAP.get(key)
            if mapped:
                fdc_id = self._ndb_index.get(mapped)
        if fdc_id is None:
            return None
        return self.get_nutrient_profile(fdc_id)

    def get_nutrient_profile(self, fdc_id: int) -> NutrientProfile | None:
        """Get the nutrient profile for a food by FDC ID."""
        if fdc_id in self._profiles:
            return self._profiles[fdc_id]

        food = self._data.get(fdc_id)
        if food is None:
            return None

        profile = self._parse_nutrients(food)
        self._profiles[fdc_id] = profile
        return profile

    def has_ndb(self, ndb_number: str | int) -> bool:
        """Check if an ndbNumber exists in the database."""
        return str(ndb_number) in self._ndb_index

    # ── Description Search ───────────────────────────────────────────────

    def search_by_name(self, name: str) -> list[NutrientProfile]:
        """Exact (case-insensitive) match by description."""
        name_lower = name.lower().strip()
        fdc_ids = self._name_index.get(name_lower, [])
        profiles = []
        for fdc_id in fdc_ids:
            profile = self.get_nutrient_profile(fdc_id)
            if profile:
                profiles.append(profile)
        return profiles

    def search_by_substring(self, name: str) -> list[tuple[NutrientProfile, float]]:
        """Search by substring containment (bidirectional).

        Handles cases like:
          "Onions, red, raw" ⊂ ? → finds "Onions, raw"
          "REDUCED SODIUM: Ham" ⊂ ? → finds "Ham"
        """
        name_lower = name.lower().strip()
        results: list[tuple[NutrientProfile, float]] = []

        for idx_name, fdc_ids in self._name_index.items():
            score = 0.0
            if name_lower in idx_name:
                # Query is substring of indexed name
                score = 80.0 + 10.0 * len(name_lower) / len(idx_name)
            elif idx_name in name_lower:
                # Indexed name is substring of query
                score = 70.0 + 10.0 * len(idx_name) / len(name_lower)

            if score > 0:
                for fdc_id in fdc_ids:
                    profile = self.get_nutrient_profile(fdc_id)
                    if profile:
                        results.append((profile, score))

        results.sort(key=lambda x: x[1], reverse=True)
        return results[:10]

    def search_by_words(self, name: str, min_overlap: int = 2) -> list[tuple[NutrientProfile, float]]:
        """Search by multi-word overlap.

        Tokenizes both query and indexed names, computes overlap.
        Handles cultivar/variety variants like:
          "Potatoes, red, without skin, raw" → "Potatoes, raw, without skin"
          "Grapes, green, seedless, raw" → "Grapes, red or green, raw"
        """
        query_words = self._tokenize(name.lower().strip())
        if len(query_words) < min_overlap:
            return self.search_by_substring(name)

        # Score each indexed food by word overlap
        scored_fdcs: dict[int, float] = {}
        candidate_fdcs: set[int] = set()

        # Only consider foods that share at least one word
        for word in query_words:
            if word in self._word_index:
                candidate_fdcs.update(self._word_index[word])

        for fdc_id in candidate_fdcs:
            food = self._data.get(fdc_id)
            if food is None:
                continue
            idx_words = self._tokenize(food.get("description", "").lower())

            overlap = len(query_words & idx_words)
            if overlap >= min_overlap:
                # Jaccard-like score weighted by overlap count
                union = len(query_words | idx_words)
                score = 60.0 + 40.0 * overlap / max(union, 1)
                scored_fdcs[fdc_id] = score

        # Build results
        results = []
        for fdc_id, score in sorted(scored_fdcs.items(), key=lambda x: x[1], reverse=True):
            profile = self.get_nutrient_profile(fdc_id)
            if profile:
                results.append((profile, score))

        return results[:10]

    def search(self, name: str) -> list[tuple[NutrientProfile, float]]:
        """Smart search: try exact → substring → word-overlap in order.

        Returns list of (profile, confidence_score) sorted by score descending.
        """
        # 1. Exact match
        exact = self.search_by_name(name)
        if exact:
            return [(p, 100.0) for p in exact]

        # 2. Substring match
        sub = self.search_by_substring(name)
        if sub:
            return sub

        # 3. Word-overlap match
        return self.search_by_words(name, min_overlap=2)

    # ── Helpers ──────────────────────────────────────────────────────────

    def _parse_nutrients(self, food: dict) -> NutrientProfile:
        """Parse nutrient records from an SR Legacy food dict."""
        nutrients = []
        for fn in food.get("foodNutrients", []):
            nut_info = fn.get("nutrient", {})
            nutrients.append(NutrientRecord(
                nutrient_id=nut_info.get("id", 0),
                nutrient_number=str(nut_info.get("number", "")),
                name=nut_info.get("name", ""),
                amount=fn.get("amount", 0.0),
                unit=nut_info.get("unitName", "g") or "g",
                rank=nut_info.get("rank"),
                derivation_code=(
                    fn.get("foodNutrientDerivation", {}).get("code")
                    if "foodNutrientDerivation" in fn
                    else None
                ),
            ))

        return NutrientProfile(
            fdc_id=food.get("fdcId"),
            description=food.get("description", ""),
            nutrients=nutrients,
            basis="per_100g",
        )

    @staticmethod
    def _tokenize(text: str) -> set[str]:
        """Tokenize text into meaningful word tokens."""
        # Remove punctuation, split on whitespace
        text = re.sub(r"[^\w\s]", " ", text)
        tokens = text.split()
        # Filter out very short/common words
        stop_words = {"and", "or", "with", "the", "for", "raw", "cooked",
                       "without", "added", "not", "from", "no", "as", "in",
                       "of", "to", "upc"}
        return {t for t in tokens if len(t) > 1 and t not in stop_words}

    def to_product_observation(self, fdc_id: int) -> None:
        """SR Legacy foods are ingredients, not products — returns None."""
        return None

    def __len__(self) -> int:
        return len(self._data)

    def __contains__(self, fdc_id: int) -> bool:
        return fdc_id in self._data
