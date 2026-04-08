"""
Grader for the Incident Report Structuring Environment.

THE BIG PROBLEM: Incident reports are messy and inconsistent.
  - "kiran.r" vs "Kiran R" → same person, different format
  - "847G" vs "847" → same number, different unit notation
  - "CF" vs "Cloudflare" → same company, abbreviated vs full name
  - "api-gw" vs "api-gateway" → same service, abbreviated vs full name

Approach: Different grading strategies for different field types.
  - "exact"    → must match exactly (after normalization)
               → used for ticket IDs, incident IDs, service versions
  - "numeric"  → extract numbers and compare
               → used for lag ms, traffic gbps, pod counts, durations
  - "contains" → ground truth must appear inside the answer (or vice versa)
               → used for timestamps, severity levels, status fields
  - "fuzzy"    → character-level similarity score (no external libraries!)
               → used for engineer names, service names, attack types
  - "list"     → compare lists of items by membership intersection
               → used for affected regions, degraded services, endpoints

Every field gets a score from 0.0 to 1.0. The overall reward is the
average of all field scores, providing natural partial credit throughout
the episode rather than sparse binary end-of-episode rewards.
"""

import re


def normalize(text: str) -> str:
    """
    Normalize a string for comparison.
    
    What this does:
      - Converts to lowercase
      - Strips leading/trailing whitespace
      - Collapses multiple spaces into one
      - Removes common punctuation noise
    
    Example:
      "  Rahul   Sharma  " → "rahul sharma"
      "New Delhi, India" → "new delhi india"
    """
    if not isinstance(text, str):
        text = str(text)
    text = text.lower().strip()
    # Remove commas, periods, and extra spaces
    text = re.sub(r'[,.\-\/\\]', ' ', text)
    text = re.sub(r'\s+', ' ', text)
    return text.strip()


def extract_numbers(text: str) -> list[float]:
    """
    Pull all numbers out of a string.
    
    Example:
      "$1,200.50" → [1200.50]
      "between 50000 and 80000" → [50000.0, 80000.0]
    """
    if not isinstance(text, str):
        text = str(text)
    # Remove commas from numbers (1,200 → 1200)
    cleaned = re.sub(r'(\d),(\d)', r'\1\2', text)
    # Find all numbers (including decimals)
    numbers = re.findall(r'\d+\.?\d*', cleaned)
    return [float(n) for n in numbers]


def similarity_score(a: str, b: str) -> float:
    """
    Calculate how similar two strings are (0.0 to 1.0).
    
    Uses a simple character-level approach (no external libraries needed):
    We count how many 2-character chunks (bigrams) they share.
    
    This is called the Sørensen–Dice coefficient.
    
    Examples:
      "new delhi" vs "delhi" → ~0.6 (decent match)
      "rahul" vs "rahul" → 1.0 (perfect)
      "apple" vs "zebra" → ~0.0 (no match)
    """
    a = normalize(a)
    b = normalize(b)
    
    if a == b:
        return 1.0
    if len(a) < 2 or len(b) < 2:
        # For very short strings, fall back to exact match
        return 1.0 if a == b else 0.0
    
    # Create bigrams (2-character chunks)
    # "hello" → {"he", "el", "ll", "lo"}
    bigrams_a = set()
    for i in range(len(a) - 1):
        bigrams_a.add(a[i:i+2])
    
    bigrams_b = set()
    for i in range(len(b) - 1):
        bigrams_b.add(b[i:i+2])
    
    # Dice coefficient = 2 * |intersection| / (|A| + |B|)
    overlap = len(bigrams_a & bigrams_b)
    total = len(bigrams_a) + len(bigrams_b)
    
    if total == 0:
        return 0.0
    
    return (2.0 * overlap) / total


def grade_field(extracted_value, expected_value, match_type: str = "fuzzy") -> float:
    """
    Grade a single extracted field against the expected value.
    
    Args:
        extracted_value: What the LLM extracted
        expected_value: The correct answer (ground truth)
        match_type: How to compare them
            - "exact": normalized exact match (0.0 or 1.0)
            - "numeric": compare as numbers
            - "contains": check if one contains the other
            - "fuzzy": similarity score (0.0 to 1.0)
            - "list": compare lists of items
    
    Returns:
        Score from 0.0 to 1.0
    """
    # Handle missing/empty values
    if extracted_value is None or extracted_value == "":
        return 0.0
    if expected_value is None or expected_value == "":
        return 0.0

    ext = str(extracted_value)
    exp = str(expected_value)

    # ── EXACT MATCH ──
    if match_type == "exact":
        return 1.0 if normalize(ext) == normalize(exp) else 0.0

    # ── NUMERIC MATCH ──
    elif match_type == "numeric":
        ext_nums = extract_numbers(ext)
        exp_nums = extract_numbers(exp)
        
        if not exp_nums:
            # Expected has no numbers — fall back to fuzzy
            return similarity_score(ext, exp)
        
        if not ext_nums:
            return 0.0
        
        # Check if any extracted number matches any expected number
        # This handles "$1,200" vs "1200" correctly
        best_score = 0.0
        for en in exp_nums:
            for xn in ext_nums:
                if en == 0 and xn == 0:
                    best_score = max(best_score, 1.0)
                elif en != 0:
                    # How close are they? (within 5% = full credit)
                    ratio = abs(xn - en) / abs(en)
                    if ratio < 0.05:
                        best_score = max(best_score, 1.0)
                    elif ratio < 0.2:
                        best_score = max(best_score, 0.5)
        
        return best_score

    # ── CONTAINS MATCH ──
    elif match_type == "contains":
        ext_norm = normalize(ext)
        exp_norm = normalize(exp)
        
        if ext_norm == exp_norm:
            return 1.0
        elif exp_norm in ext_norm or ext_norm in exp_norm:
            return 0.8
        else:
            # Check for acronym match:
            # "TCS" could be an acronym for "Tata Consultancy Services"
            ext_upper = ext.strip().upper()
            exp_words = exp.strip().split()
            if len(ext_upper) <= 6 and ext_upper.isalpha():
                # Build acronym from expected value's first letters
                acronym = "".join(w[0].upper() for w in exp_words if w)
                if ext_upper == acronym:
                    return 0.85
            # Also check reverse — expected is acronym of extracted
            exp_upper = exp.strip().upper()
            ext_words = ext.strip().split()
            if len(exp_upper) <= 6 and exp_upper.isalpha():
                acronym = "".join(w[0].upper() for w in ext_words if w)
                if exp_upper == acronym:
                    return 0.85
            # Fall back to fuzzy
            return similarity_score(ext, exp) * 0.7

    # ── LIST MATCH ──
    elif match_type == "list":
        # Both should be lists. Compare items.
        if isinstance(expected_value, list) and isinstance(extracted_value, list):
            if len(expected_value) == 0:
                return 1.0 if len(extracted_value) == 0 else 0.0
            
            matched = 0
            for exp_item in expected_value:
                for ext_item in extracted_value:
                    if similarity_score(str(ext_item), str(exp_item)) > 0.7:
                        matched += 1
                        break
            
            return matched / len(expected_value)
        else:
            # Not lists — fall back to fuzzy on string representation
            return similarity_score(str(extracted_value), str(expected_value))

    # ── FUZZY MATCH (default) ──
    else:
        score = similarity_score(ext, exp)
        # Boost: if normalized versions are equal, that's perfect
        if normalize(ext) == normalize(exp):
            return 1.0
        # Boost: if one contains the other, minimum 0.6
        if normalize(exp) in normalize(ext) or normalize(ext) in normalize(exp):
            return max(score, 0.6)
        return score


def grade_extraction(extracted_data: dict, ground_truth: dict, field_types: dict) -> dict:
    """
    Grade an entire extraction (all fields at once).
    
    Args:
        extracted_data: What the LLM extracted (dict of field→value)
        ground_truth: The correct answers (dict of field→value)
        field_types: How to grade each field (dict of field→match_type)
    
    Returns:
        {
            "field_scores": {"name": 1.0, "email": 0.8, ...},
            "fields_correct": 3,      # fields with score >= 0.8
            "fields_total": 5,
            "reward": 0.72,           # average of all field scores
            "feedback_lines": ["✓ name: ...", "✗ email: ...", ...]
        }
    """
    field_scores = {}
    feedback_lines = []
    
    for field_name, expected_value in ground_truth.items():
        match_type = field_types.get(field_name, "fuzzy")
        extracted_value = extracted_data.get(field_name, "")
        
        score = grade_field(extracted_value, expected_value, match_type)
        field_scores[field_name] = round(score, 3)
        
        # Build feedback
        if score >= 0.8:
            feedback_lines.append(
                f"  ✓ {field_name}: extracted='{extracted_value}' "
                f"expected='{expected_value}' → score={score:.2f}"
            )
        elif score > 0.3:
            feedback_lines.append(
                f"  △ {field_name}: extracted='{extracted_value}' "
                f"expected='{expected_value}' → score={score:.2f} (partial)"
            )
        else:
            feedback_lines.append(
                f"  ✗ {field_name}: extracted='{extracted_value}' "
                f"expected='{expected_value}' → score={score:.2f}"
            )
    
    fields_correct = sum(1 for s in field_scores.values() if s >= 0.8)
    fields_total = len(ground_truth)
    
    # Overall reward = average of field scores, clamped to strict (0, 1)
    reward = sum(field_scores.values()) / fields_total if fields_total > 0 else 0.0
    reward = round(max(0.001, min(0.999, reward)), 3)
    
    return {
        "field_scores": field_scores,
        "fields_correct": fields_correct,
        "fields_total": fields_total,
        "reward": reward,
        "feedback_lines": feedback_lines,
    }