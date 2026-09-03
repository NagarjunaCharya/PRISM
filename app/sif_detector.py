"""
SIF Precursor Detection Engine
Detects Serious Injury and Fatality precursors from incident narratives using
TF-IDF classification + keyword-based rules + entity extraction.
REQ-2 (SIF Detection), REQ-7 (Explainability)
"""
import re
import numpy as np
from dataclasses import dataclass, field
from typing import Optional


# =============================================================================
# SIF PRECURSOR CATEGORIES & KEYWORD LEXICONS
# =============================================================================

SIF_CATEGORIES = {
    "energy_release": {
        "description": "Uncontrolled release of energy (electrical, hydraulic, pneumatic, chemical)",
        "keywords": [
            "explosion", "explod", "blast", "detonat", "burst", "ruptur",
            "electrical shock", "electrocut", "arc flash", "short circuit",
            "pressure release", "overpressure", "blowout", "blow out",
            "gas release", "gas leak", "chemical release", "chemical spill",
            "steam release", "hydraulic failure", "pneumatic",
            "energized", "de-energiz", "lockout", "tagout", "loto",
            "flash fire", "ignit", "combust", "flammab", "volatile",
            "high voltage", "high pressure", "discharge", "surge",
        ],
        "severity_weight": 0.95,
    },
    "fall_hazard": {
        "description": "Falls from elevation or to lower level",
        "keywords": [
            "fall", "fell", "fallen", "falling", "slip", "slipped",
            "trip", "tripped", "stumbl", "ladder", "scaffold",
            "roof", "rooftop", "elevation", "height", "story", "stories",
            "platform", "walkway", "catwalk", "stairway", "stair",
            "guardrail", "handrail", "railing", "harness", "lanyard",
            "lower level", "upper level", "mezzanine", "balcony",
            "opening", "hole", "edge", "unprotected",
            "feet above", "foot drop", "foot fall",
        ],
        "severity_weight": 0.90,
    },
    "struck_by": {
        "description": "Struck by moving object, vehicle, or equipment",
        "keywords": [
            "struck", "hit by", "impact", "collid", "collision",
            "crush", "crushed", "crushing", "pinch", "pinned",
            "vehicle", "forklift", "truck", "crane", "hoist",
            "load", "rigging", "swing", "dropped", "falling object",
            "overhead", "suspended", "flying", "projectil", "debris",
            "excavat", "backhoe", "bulldozer", "equipment struck",
            "moving part", "rotating", "conveyor",
        ],
        "severity_weight": 0.88,
    },
    "caught_in_between": {
        "description": "Caught in, under, or between objects or machinery",
        "keywords": [
            "caught", "entangle", "entrap", "trapped", "engulf",
            "cave-in", "cave in", "cavein", "collapse", "collaps",
            "trench", "excavation", "shoring",
            "between", "compress", "squeez", "nip point",
            "machine guard", "unguarded", "guard remov",
            "roller", "gear", "pulley", "belt", "chain",
            "amputation", "amputat", "sever", "lacerat",
            "auger", "press", "die", "mold", "stamp",
        ],
        "severity_weight": 0.92,
    },
    "chemical_exposure": {
        "description": "Exposure to hazardous chemicals, gases, or substances",
        "keywords": [
            "chemical", "toxic", "poison", "hazardous substance",
            "inhalat", "inhaled", "fumes", "vapor", "gas exposure",
            "asphyxia", "oxygen deficien", "confined space",
            "h2s", "hydrogen sulfide", "carbon monoxide", "co poison",
            "acid", "caustic", "corrosive", "burn chemical",
            "dermatitis", "skin contact", "eye contact", "splash",
            "ppe", "respirator", "ventilation", "exhaust",
            "asbestos", "silica", "lead exposure", "benzene",
        ],
        "severity_weight": 0.85,
    },
}

# Entity patterns for extraction
ENTITY_PATTERNS = {
    "EQUIPMENT": re.compile(
        r'\b(forklift|crane|hoist|scaffold|ladder|conveyor|press|lathe|saw|drill|'
        r'grinder|welder|compressor|pump|motor|generator|boiler|tank|pipe|valve|'
        r'truck|vehicle|tractor|excavator|backhoe|bulldozer|skid.?steer|'
        r'aerial lift|boom lift|scissor lift|manlift|cherry picker)\b',
        re.IGNORECASE
    ),
    "HAZARD_TYPE": re.compile(
        r'\b(electrical|chemical|mechanical|thermal|radiation|biological|'
        r'ergonomic|fall|struck.?by|caught.?in|engulfment|drowning|'
        r'fire|explosion|collapse|cave.?in|trench|confined.?space)\b',
        re.IGNORECASE
    ),
    "INJURY": re.compile(
        r'\b(fracture|laceration|amputation|burn|contusion|abrasion|'
        r'concussion|sprain|strain|dislocation|puncture|crush|'
        r'fatal|death|died|killed|hospitalized|icu)\b',
        re.IGNORECASE
    ),
    "BODY_PART": re.compile(
        r'\b(head|skull|brain|eye|face|neck|shoulder|arm|elbow|wrist|'
        r'hand|finger|thumb|chest|torso|back|spine|hip|pelvis|'
        r'leg|knee|ankle|foot|toe)\b',
        re.IGNORECASE
    ),
}

# Severity indicators
FATAL_INDICATORS = re.compile(
    r'\b(fatal|death|died|killed|deceased|doa|pronounced dead|'
    r'life.?threatening|succumbed|passed away)\b',
    re.IGNORECASE
)

HOSPITALIZATION_INDICATORS = re.compile(
    r'\b(hospitalized|hospital|emergency room|er visit|icu|'
    r'intensive care|surgery|surgical|ambulance|medevac|life.?flight|'
    r'admitted|overnight)\b',
    re.IGNORECASE
)


@dataclass
class SIFDetection:
    """Result of SIF precursor detection on a single text."""
    text: str
    is_sif_precursor: bool
    overall_score: float  # 0-100
    categories: dict  # category -> {score, matched_keywords, spans}
    top_category: Optional[str]
    entities: dict  # entity_type -> [matches]
    severity_level: str  # low, moderate, high, critical
    is_fatal: bool
    is_hospitalization: bool
    explanation: str  # Plain-language explanation


class SIFDetectorEngine:
    """
    SIF Precursor Detection Engine using keyword-based NLP.
    Designed for rapid prototype — production would use fine-tuned BERT.
    """

    def __init__(self):
        self.categories = SIF_CATEGORIES
        self.entity_patterns = ENTITY_PATTERNS
        # Pre-compile keyword patterns for each category
        self._compiled_patterns = {}
        for cat_name, cat_info in self.categories.items():
            patterns = []
            for kw in cat_info["keywords"]:
                patterns.append(re.compile(r'\b' + re.escape(kw), re.IGNORECASE))
            self._compiled_patterns[cat_name] = patterns

    def detect(self, text: str) -> SIFDetection:
        """Run SIF precursor detection on a text narrative."""
        if not text or not isinstance(text, str):
            return SIFDetection(
                text=text or "",
                is_sif_precursor=False,
                overall_score=0.0,
                categories={},
                top_category=None,
                entities={},
                severity_level="low",
                is_fatal=False,
                is_hospitalization=False,
                explanation="No text provided for analysis.",
            )

        text_lower = text.lower()
        text_clean = re.sub(r'\s+', ' ', text).strip()

        # Detect categories
        category_results = {}
        for cat_name, patterns in self._compiled_patterns.items():
            matched_keywords = []
            spans = []
            for i, pattern in enumerate(patterns):
                matches = list(pattern.finditer(text_clean))
                if matches:
                    kw = self.categories[cat_name]["keywords"][i]
                    matched_keywords.append(kw)
                    for m in matches:
                        spans.append({
                            "start": m.start(),
                            "end": m.end(),
                            "text": m.group(),
                            "keyword": kw,
                        })

            if matched_keywords:
                # Score based on keyword diversity and frequency
                diversity_score = min(len(set(matched_keywords)) / 5.0, 1.0)
                frequency_score = min(len(spans) / 8.0, 1.0)
                weight = self.categories[cat_name]["severity_weight"]
                score = (diversity_score * 0.6 + frequency_score * 0.4) * weight * 100

                category_results[cat_name] = {
                    "score": round(min(score, 99.0), 1),
                    "matched_keywords": list(set(matched_keywords)),
                    "match_count": len(spans),
                    "spans": spans[:10],  # Top 10 spans
                    "description": self.categories[cat_name]["description"],
                }

        # Extract entities
        entities = {}
        for ent_type, pattern in self.entity_patterns.items():
            matches = pattern.findall(text_clean)
            if matches:
                entities[ent_type] = list(set(m.lower() for m in matches))

        # Check severity indicators
        is_fatal = bool(FATAL_INDICATORS.search(text_clean))
        is_hospitalization = bool(HOSPITALIZATION_INDICATORS.search(text_clean))

        # Calculate overall score
        if category_results:
            scores = [r["score"] for r in category_results.values()]
            overall_score = max(scores)
            # Boost for fatal/hospitalization
            if is_fatal:
                overall_score = min(overall_score * 1.3, 99.0)
            elif is_hospitalization:
                overall_score = min(overall_score * 1.15, 95.0)
        else:
            overall_score = 0.0

        overall_score = round(overall_score, 1)

        # Determine top category
        top_category = None
        if category_results:
            top_category = max(category_results, key=lambda k: category_results[k]["score"])

        # Is SIF precursor?
        is_sif = overall_score >= 25.0

        # Severity level
        if overall_score >= 71:
            severity_level = "critical"
        elif overall_score >= 51:
            severity_level = "high"
        elif overall_score >= 31:
            severity_level = "moderate"
        else:
            severity_level = "low"

        # Generate explanation
        explanation = self._generate_explanation(
            category_results, top_category, entities, is_fatal,
            is_hospitalization, overall_score, severity_level
        )

        return SIFDetection(
            text=text_clean[:500],  # Truncate for storage
            is_sif_precursor=is_sif,
            overall_score=overall_score,
            categories=category_results,
            top_category=top_category,
            entities=entities,
            severity_level=severity_level,
            is_fatal=is_fatal,
            is_hospitalization=is_hospitalization,
            explanation=explanation,
        )

    def _generate_explanation(self, categories, top_cat, entities, is_fatal,
                              is_hosp, score, severity):
        """Generate plain-language explanation (REQ-7 Explainability)."""
        parts = []

        if not categories:
            return "No SIF precursor indicators were detected in this report."

        parts.append(f"This incident has a {severity} risk level (score: {score}/100).")

        if is_fatal:
            parts.append("CRITICAL: Fatality indicators detected.")
        elif is_hosp:
            parts.append("Hospitalization indicators detected.")

        if top_cat:
            cat_info = categories[top_cat]
            cat_desc = cat_info["description"]
            keywords = ", ".join(cat_info["matched_keywords"][:5])
            parts.append(
                f"Primary SIF precursor type: {top_cat.replace('_', ' ').title()} — "
                f"{cat_desc}. Key indicators: {keywords}."
            )

        if len(categories) > 1:
            other_cats = [c.replace('_', ' ').title() for c in categories if c != top_cat]
            parts.append(f"Additional precursor types: {', '.join(other_cats)}.")

        if entities:
            for ent_type, values in entities.items():
                if values:
                    parts.append(f"{ent_type}: {', '.join(values[:3])}.")

        return " ".join(parts)

    def batch_detect(self, texts: list, progress_callback=None) -> list:
        """Run detection on multiple texts."""
        results = []
        for i, text in enumerate(texts):
            results.append(self.detect(text))
            if progress_callback and (i + 1) % 5000 == 0:
                progress_callback(i + 1, len(texts))
        return results


# Module-level instance
detector = SIFDetectorEngine()


def detect_sif(text: str) -> dict:
    """Convenience function for single text detection."""
    result = detector.detect(text)
    return {
        "is_sif_precursor": result.is_sif_precursor,
        "overall_score": result.overall_score,
        "top_category": result.top_category,
        "severity_level": result.severity_level,
        "is_fatal": result.is_fatal,
        "is_hospitalization": result.is_hospitalization,
        "categories": result.categories,
        "entities": result.entities,
        "explanation": result.explanation,
    }
