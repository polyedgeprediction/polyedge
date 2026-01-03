"""
Event Category enumeration.
"""
import re
from enum import Enum


class EventCategory(Enum):
    POLITICS = "POLITICS"
    SPORTS = "SPORTS"
    CRYPTO = "CRYPTO"
    CULTURE = "CULTURE"
    MENTIONS = "MENTIONS"
    WEATHER = "WEATHER"
    ECONOMY = "ECONOMY"
    TECH = "TECH"
    FINANCE = "FINANCE"
    OTHERS = "OTHERS"

    @classmethod
    def get_all_categories(cls):
        """Get all category values as a list of strings."""
        return [category.value for category in cls if category != cls.OTHERS]

    @classmethod
    def findCategoryFromTags(cls, label: str) -> str:
        if not label:
            return cls.OTHERS.value
        
        label_upper = label.upper().strip()
        
        # Check for exact matches first
        for category in cls:
            if category.value.upper() == label_upper:
                return category.value
        
        # Check for partial matches (e.g., "Crypto Prices" contains "CRYPTO")
        # Match if category appears as a word (at start, end, or with spaces/hyphens)
        for category_value in cls.get_all_categories():
            category_upper = category_value.upper()
            # Check if category appears in the label
            if category_upper in label_upper:
                # Ensure it's a whole word match (not part of another word)
                # Check boundaries: start of string, space, hyphen, or end of string
                pattern = r'(^|[\s-])' + re.escape(category_upper) + r'([\s-]|$)'
                if re.search(pattern, label_upper):
                    return category_value
        
        return cls.OTHERS.value

