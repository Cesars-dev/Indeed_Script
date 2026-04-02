"""
Pattern registry — known answer mappings for SmartApply questions.
Static patterns here, dynamic patterns loaded from Supabase at startup.
"""

# ── Yes/No radio patterns ─────────────────────────────────────────────────────
# Key = lowercase substring found in question text → Value = answer
YESNO_ANSWERS: dict[str, str] = {
    # Work authorization
    "authorized to work": "Yes",
    "legally authorized": "Yes",
    "work in the united states": "Yes",
    "eligible to work": "Yes",
    "require sponsorship": "No",
    "need sponsorship": "No",
    "visa sponsorship": "No",
    # Language
    "speak spanish": "Yes",
    "habla español": "Yes",
    "bilingual": "Yes",
    # Education
    "high school diploma": "Yes",
    "ged": "Yes",
    # Transportation & location
    "reliable transportation": "Yes",
    "reliably commute": "Yes",
    "valid driver": "Yes",
    "willing to relocate": "Yes",
    # Background & compliance
    "background check": "Yes",
    "drug test": "Yes",
    "drug screen": "Yes",
    # Age
    "18 years": "Yes",
    "at least 18": "Yes",
    "21 years": "Yes",
    "at least 21": "Yes",
    # Employment
    "currently employed": "No",
    "non-compete": "No",
    "previously employed": "No",
    "previously worked": "No",
    # Certifications — default No (specialized)
    "cdl": "No",
    "commercial driver": "No",
    "forklift": "No",
    "cna": "No",
    "rn license": "No",
    "lpn": "No",
}

# ── Range/enum radio patterns ─────────────────────────────────────────────────
# Key = keyword in question → Value = preferred answer text
RANGE_ANSWERS: dict[str, str] = {
    "years of experience": "2 - 5 years",
    "microsoft office": "2 - 5 years",
    "customer service": "2 - 5 years",
    "data entry": "2 - 5 years",
    "medical": "1 - 2 years",
    "travel": "Less than 20%",
    "willing to travel": "Less than 20%",
    "overtime": "Yes",
    "shift": "Day shift",
    "schedule": "Full-time",
    "employment type": "Full-time",
    "start date": "Immediately",
    "availability": "Immediately",
    "when can you start": "Immediately",
    "education level": "High School Diploma",
}

# ── Text input mappings ───────────────────────────────────────────────────────
# Key = keyword in label → Value = profile field name
TEXT_FIELD_MAP: dict[str, str] = {
    "phone": "phone",
    "mobile": "phone",
    "cell": "phone",
    "telephone": "phone",
    "hourly": "salary_hr",
    "wage": "salary_hr",
    "pay rate": "salary_hr",
    "annual salary": "salary_yr",
    "yearly salary": "salary_yr",
    "salary expectation": "salary_yr",
    "desired salary": "salary_yr",
    "compensation": "salary_yr",
    "years of experience": "years_exp",
    "years experience": "years_exp",
    "total experience": "years_exp",
}

# Default values when no profile field matches but we recognize the type
TEXT_DEFAULTS: dict[str, str] = {
    "years": "3",
    "experience": "3",
    "gpa": "3.5",
    "zip": "84101",
}


# ── Matchers ──────────────────────────────────────────────────────────────────

def match_yesno(question: str) -> str | None:
    """Return 'Yes'/'No' if question matches a known Yes/No pattern."""
    q = question.lower()
    for keyword, answer in YESNO_ANSWERS.items():
        if keyword in q:
            return answer
    return None


def match_range(question: str, options: list[str]) -> str | None:
    """Return best matching option text for a range/enum question."""
    q = question.lower()
    for keyword, preferred in RANGE_ANSWERS.items():
        if keyword in q:
            pref_lower = preferred.lower()
            # Try exact match first
            for opt in options:
                if opt.lower().strip() == pref_lower:
                    return opt
            # Try substring match
            for opt in options:
                if pref_lower in opt.lower() or opt.lower() in pref_lower:
                    return opt
            # Word overlap match
            pref_words = set(pref_lower.split())
            best_score, best_opt = 0, None
            for opt in options:
                overlap = len(pref_words & set(opt.lower().split()))
                if overlap > best_score:
                    best_score = overlap
                    best_opt = opt
            if best_opt and best_score > 0:
                return best_opt
            # Last resort: first non-empty option
            return options[0] if options else None
    return None


def match_text_input(label: str, profile: dict) -> str | None:
    """Return value to fill if label matches a known text pattern."""
    lab = label.lower()
    # Try profile fields first
    for keyword, field in TEXT_FIELD_MAP.items():
        if keyword in lab:
            val = profile.get(field, "")
            if val:
                return str(val)
    # Try defaults
    for keyword, default in TEXT_DEFAULTS.items():
        if keyword in lab:
            return default
    return None


# ── Dynamic patterns from Supabase ────────────────────────────────────────────
_dynamic_patterns: list[dict] = []


def load_dynamic_patterns():
    """Load learned patterns from Supabase apply_patterns table at startup."""
    global _dynamic_patterns
    try:
        import requests
        import os
        url = os.getenv("SUPABASE_URL", "")
        key = os.getenv("SUPABASE_KEY", "")
        if not url or not key:
            return
        r = requests.get(
            f"{url}/rest/v1/apply_patterns",
            params={"select": "*", "order": "created_at.desc"},
            headers={
                "apikey": key,
                "Authorization": f"Bearer {key}",
            },
            timeout=10,
        )
        if r.ok:
            _dynamic_patterns = r.json()
            print(f"[patterns] Loaded {len(_dynamic_patterns)} dynamic patterns")
    except Exception as e:
        print(f"[patterns] Could not load dynamic patterns: {e}")


def get_dynamic_answer(question: str) -> tuple[str, str] | None:
    """Check dynamic patterns for a matching question. Returns (answer_type, answer_value) or None."""
    q = question.lower()
    for pat in _dynamic_patterns:
        keyword = pat.get("question_text", "").lower()
        if keyword and keyword in q:
            return (pat.get("answer_type", ""), pat.get("answer_value", ""))
    return None
