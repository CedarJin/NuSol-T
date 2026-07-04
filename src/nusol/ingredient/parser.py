"""Ingredient list parser — converts ingredient text to IngredientTree."""

from __future__ import annotations

import re

from nusol.core.schema import IngredientNode, IngredientTree


class IngredientParser:
    """Parse a packaged food ingredient list string into an IngredientTree.

    Handles:
      - Comma-separated main ingredients
      - Parenthetical sub-ingredients: "COCOA (PROCESSED WITH ALKALI)"
      - "CONTAINS 2% OR LESS OF:" separator
      - Period-terminated ingredient lists
      - Asterisk/footnote markers
    """

    TWO_PCT_PATTERNS = [
        re.compile(r"contains\s+(less\s+than\s+)?2%\s+(or\s+less\s+)?of\s*[:;—-]?", re.IGNORECASE),
        re.compile(r"2%\s+(or\s+less\s+)?of\s*[:;—-]?", re.IGNORECASE),
    ]

    def parse(self, text: str) -> IngredientTree:
        """Parse an ingredient list string.

        Args:
            text: Raw ingredient list text from a product label.

        Returns:
            IngredientTree with parsed structure.
        """
        text = self._preprocess(text)

        # Split into main list and ≤2% group
        main_text, two_pct_text = self._split_two_percent(text)

        # Parse each section
        root_ingredients = self._parse_section(main_text, is_main=True)
        two_percent_group = self._parse_section(two_pct_text, is_main=False) if two_pct_text else []

        # Mark ≤2% group
        for ing in two_percent_group:
            ing.is_low_impact = True

        return IngredientTree(
            raw_text=text,
            root_ingredients=root_ingredients,
            two_percent_group=two_percent_group,
        )

    def _preprocess(self, text: str) -> str:
        """Clean ingredient text."""
        # Strip leading/trailing whitespace
        text = text.strip()
        # Remove trailing period
        if text.endswith(".") and not text.endswith(".."):
            text = text[:-1]
        # Normalize whitespace
        text = re.sub(r"\s+", " ", text)
        return text

    def _split_two_percent(self, text: str) -> tuple[str, str]:
        """Split text into main ingredients and ≤2% ingredients."""
        for pattern in self.TWO_PCT_PATTERNS:
            m = pattern.search(text)
            if m:
                idx = m.start()
                return text[:idx].strip(), text[m.end():].strip()
        return text, ""

    def _parse_section(self, text: str, is_main: bool = True) -> list[IngredientNode]:
        """Parse a section of ingredient text into nodes."""
        if not text.strip():
            return []

        # Split by comma, respecting parentheses
        parts = self._smart_split(text)

        ingredients = []
        for pos, part in enumerate(parts):
            part = part.strip()
            if not part:
                continue

            node = self._parse_single_ingredient(part, pos, is_main)
            ingredients.append(node)

        return ingredients

    def _smart_split(self, text: str) -> list[str]:
        """Split by comma while respecting parentheses."""
        parts = []
        depth = 0
        current = []

        for ch in text:
            if ch == "(":
                depth += 1
                current.append(ch)
            elif ch == ")":
                depth -= 1
                current.append(ch)
            elif ch == "," and depth == 0:
                parts.append("".join(current))
                current = []
            else:
                current.append(ch)

        if current:
            parts.append("".join(current))

        return parts

    def _parse_single_ingredient(
        self, text: str, position: int, is_main: bool
    ) -> IngredientNode:
        """Parse a single ingredient entry, extracting parenthetical sub-ingredients."""
        text = text.strip()

        # Remove asterisk/footnote markers
        text = re.sub(r"\*+", "", text)
        text = re.sub(r"†+", "", text)

        # Extract parenthetical content
        parenthetical_text = None
        children = []
        is_compound = False

        # Find parenthetical groups
        paren_match = re.search(r"\(([^)]+)\)", text)
        if paren_match:
            parenthetical_text = paren_match.group(1)
            # Parse sub-ingredients from parenthetical
            sub_parts = self._smart_split(parenthetical_text)
            for sub_pos, sub_part in enumerate(sub_parts):
                sub_part = sub_part.strip()
                if sub_part:
                    children.append(IngredientNode(
                        name=sub_part,
                        normalized_name=sub_part.lower().strip(),
                        position=sub_pos,
                        is_sub_ingredient=True,
                    ))
            is_compound = True
            # Remove parenthetical from main name
            text = re.sub(r"\s*\([^)]+\)\s*", " ", text).strip()

        # Clean up AND/OR
        text = re.sub(r"\s+and/or\s+", " or ", text, flags=re.IGNORECASE)

        return IngredientNode(
            name=text,
            normalized_name=text.lower().strip(),
            position=position,
            is_compound=is_compound,
            parenthetical_text=parenthetical_text,
            children=children,
        )

    def parse_simple(self, comma_separated: str) -> IngredientTree:
        """Parse a simple comma-separated ingredient list (no complex structures).

        This is used for FNDDS-style ingredient lists where the text is simply
        comma-separated ingredient names.
        """
        text = self._preprocess(comma_separated)
        parts = [p.strip() for p in text.split(",") if p.strip()]

        ingredients = [
            IngredientNode(
                name=part,
                normalized_name=part.lower().strip(),
                position=i,
            )
            for i, part in enumerate(parts)
        ]

        return IngredientTree(
            raw_text=comma_separated,
            root_ingredients=ingredients,
        )
