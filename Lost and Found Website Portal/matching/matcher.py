import re
import math
from datetime import datetime
from difflib import SequenceMatcher

# Weights defined by SmartRecover specifications:
# 1. Item name and keywords: 30% (0.30)
# 2. Category: 20% (0.20)
# 3. Description similarity: 25% (0.25)
# 4. Location similarity: 15% (0.15)
# 5. Date proximity: 10% (0.10)
WEIGHT_NAME = 0.30
WEIGHT_CATEGORY = 0.20
WEIGHT_DESCRIPTION = 0.25
WEIGHT_LOCATION = 0.15
WEIGHT_DATE = 0.10

COMMON_STOPWORDS = {
    'a', 'an', 'the', 'and', 'or', 'in', 'on', 'at', 'to', 'for', 'with', 'by',
    'my', 'mine', 'of', 'from', 'is', 'was', 'are', 'were', 'it', 'its', 'lost',
    'found', 'has', 'have', 'had', 'any', 'some', 'this', 'that', 'near', 'inside'
}

def clean_and_tokenize(text):
    """
    Normalizes text to lowercase, strips punctuation, and extracts keywords.
    """
    if not text:
        return []
    cleaned = re.sub(r'[^\w\s]', ' ', str(text).lower())
    tokens = [w.strip() for w in cleaned.split() if w.strip()]
    return tokens

def clean_text(text):
    """
    Returns normalized text without extra spaces or punctuation.
    """
    if not text:
        return ""
    return re.sub(r'\s+', ' ', re.sub(r'[^\w\s]', ' ', str(text).lower())).strip()

def compute_token_overlap(tokens_a, tokens_b, filter_stopwords=True):
    """
    Calculates Jaccard similarity and token overlap between two token lists.
    """
    if filter_stopwords:
        set_a = {t for t in tokens_a if t not in COMMON_STOPWORDS and len(t) > 1}
        set_b = {t for t in tokens_b if t not in COMMON_STOPWORDS and len(t) > 1}
    else:
        set_a = set(tokens_a)
        set_b = set(tokens_b)

    if not set_a or not set_b:
        # Fallback to unfiltered if all words were stopwords
        set_a = set(tokens_a)
        set_b = set(tokens_b)
        if not set_a or not set_b:
            return 0.0

    intersection = set_a.intersection(set_b)
    union = set_a.union(set_b)
    return len(intersection) / len(union) if union else 0.0

def compute_string_similarity(str_a, str_b):
    """
    Uses Python standard library SequenceMatcher for character sequence similarity.
    """
    clean_a = clean_text(str_a)
    clean_b = clean_text(str_b)
    if not clean_a or not clean_b:
        return 0.0
    return SequenceMatcher(None, clean_a, clean_b).ratio()

def compute_name_score(name_a, name_b):
    """
    Blends sequence similarity with keyword token overlap for item names.
    """
    seq_sim = compute_string_similarity(name_a, name_b)
    tokens_a = clean_and_tokenize(name_a)
    tokens_b = clean_and_tokenize(name_b)
    overlap = compute_token_overlap(tokens_a, tokens_b)
    # Blend: 50% sequence similarity, 50% keyword overlap
    return min(1.0, (seq_sim * 0.5) + (overlap * 0.5))

def compute_category_score(cat_a, cat_b):
    """
    Checks if categories match directly or hierarchically.
    """
    norm_a = clean_text(cat_a)
    norm_b = clean_text(cat_b)
    if not norm_a or not norm_b:
        return 0.0
    if norm_a == norm_b:
        return 1.0
    if norm_a in norm_b or norm_b in norm_a:
        return 0.75
    return 0.0

def compute_description_score(desc_a, desc_b):
    """
    Description similarity combining token overlap and SequenceMatcher.
    """
    clean_a = clean_text(desc_a)
    clean_b = clean_text(desc_b)
    if not clean_a or not clean_b:
        return 0.0
    
    tokens_a = clean_and_tokenize(desc_a)
    tokens_b = clean_and_tokenize(desc_b)
    overlap = compute_token_overlap(tokens_a, tokens_b, filter_stopwords=True)
    seq = SequenceMatcher(None, clean_a, clean_b).ratio()
    return min(1.0, (overlap * 0.7) + (seq * 0.3))

def compute_location_score(loc_a, loc_b):
    """
    Location similarity based on landmark/building keywords and sequence match.
    """
    clean_a = clean_text(loc_a)
    clean_b = clean_text(loc_b)
    if not clean_a or not clean_b:
        return 0.0
    if clean_a == clean_b:
        return 1.0
    tokens_a = clean_and_tokenize(loc_a)
    tokens_b = clean_and_tokenize(loc_b)
    overlap = compute_token_overlap(tokens_a, tokens_b, filter_stopwords=False)
    seq = SequenceMatcher(None, clean_a, clean_b).ratio()
    return min(1.0, (overlap * 0.6) + (seq * 0.4))

def compute_date_score(date_a, date_b):
    """
    Calculates date proximity score.
    Higher score for items lost and found within close days.
    """
    try:
        if isinstance(date_a, str):
            dt_a = datetime.strptime(str(date_a)[:10], '%Y-%m-%d').date()
        elif hasattr(date_a, 'date'):
            dt_a = date_a.date()
        else:
            dt_a = date_a

        if isinstance(date_b, str):
            dt_b = datetime.strptime(str(date_b)[:10], '%Y-%m-%d').date()
        elif hasattr(date_b, 'date'):
            dt_b = date_b.date()
        else:
            dt_b = date_b

        diff_days = abs((dt_a - dt_b).days)
        
        # Proximity decay:
        if diff_days <= 1:
            return 1.0
        elif diff_days <= 3:
            return 0.90
        elif diff_days <= 7:
            return 0.75
        elif diff_days <= 14:
            return 0.50
        elif diff_days <= 30:
            return 0.25
        elif diff_days <= 60:
            return 0.10
        else:
            return 0.05
    except Exception:
        return 0.20

def calculate_similarity_breakdown(lost_item, found_item):
    """
    Computes exact factor scores and weighted final score (0.0 to 100.0).
    """
    raw_name = compute_name_score(lost_item.get('name', ''), found_item.get('name', ''))
    raw_category = compute_category_score(lost_item.get('category', ''), found_item.get('category', ''))
    raw_desc = compute_description_score(lost_item.get('description', ''), found_item.get('description', ''))
    raw_loc = compute_location_score(lost_item.get('location', ''), found_item.get('location', ''))
    raw_date = compute_date_score(lost_item.get('date_event', ''), found_item.get('date_event', ''))

    # Weighted contributions:
    contrib_name = raw_name * WEIGHT_NAME * 100
    contrib_category = raw_category * WEIGHT_CATEGORY * 100
    contrib_desc = raw_desc * WEIGHT_DESCRIPTION * 100
    contrib_loc = raw_loc * WEIGHT_LOCATION * 100
    contrib_date = raw_date * WEIGHT_DATE * 100

    total_score = round(contrib_name + contrib_category + contrib_desc + contrib_loc + contrib_date, 1)
    total_score = min(100.0, max(0.0, total_score))

    # Label classification per specifications
    if total_score >= 80.0:
        label = "Strong Possible Match"
        badge_class = "match-strong"
    elif total_score >= 60.0:
        label = "Potential Match"
        badge_class = "match-potential"
    else:
        label = "Low Similarity"
        badge_class = "match-low"

    return {
        "score": total_score,
        "label": label,
        "badge_class": badge_class,
        "factors": {
            "name": {
                "weight": int(WEIGHT_NAME * 100),
                "score": round(raw_name * 100, 1),
                "contribution": round(contrib_name, 1)
            },
            "category": {
                "weight": int(WEIGHT_CATEGORY * 100),
                "score": round(raw_category * 100, 1),
                "contribution": round(contrib_category, 1)
            },
            "description": {
                "weight": int(WEIGHT_DESCRIPTION * 100),
                "score": round(raw_desc * 100, 1),
                "contribution": round(contrib_desc, 1)
            },
            "location": {
                "weight": int(WEIGHT_LOCATION * 100),
                "score": round(raw_loc * 100, 1),
                "contribution": round(contrib_loc, 1)
            },
            "date": {
                "weight": int(WEIGHT_DATE * 100),
                "score": round(raw_date * 100, 1),
                "contribution": round(contrib_date, 1)
            }
        }
    }

class SmartMatcher:
    """
    Python-powered Smart Matching Engine for Lost & Found items.
    """
    @staticmethod
    def evaluate_pair(lost_item, found_item):
        """
        Validates business rules and evaluates match.
        """
        # Cross-institution check
        if lost_item.get('institution_id') != found_item.get('institution_id'):
            return None
        
        # Verify types
        if lost_item.get('type') != 'lost' or found_item.get('type') != 'found':
            return None
        
        # Avoid already returned items
        if lost_item.get('status') in ('recovered', 'closed') or found_item.get('status') in ('recovered', 'closed'):
            return None

        # Calculate similarity
        breakdown = calculate_similarity_breakdown(lost_item, found_item)
        return breakdown

    @staticmethod
    def match_item_against_pool(target_item, candidate_items, min_threshold=35.0):
        """
        Compares a single target item against an array of candidate items from the same institution.
        Returns ranked list of matches.
        """
        results = []
        is_lost = target_item.get('type') == 'lost'

        for candidate in candidate_items:
            # Candidate must be opposite type and same institution
            if candidate.get('id') == target_item.get('id'):
                continue
            if candidate.get('institution_id') != target_item.get('institution_id'):
                continue
            if candidate.get('status') in ('recovered', 'closed'):
                continue
            
            if is_lost and candidate.get('type') == 'found':
                eval_res = SmartMatcher.evaluate_pair(target_item, candidate)
                lost_ref = target_item
                found_ref = candidate
            elif not is_lost and candidate.get('type') == 'lost':
                eval_res = SmartMatcher.evaluate_pair(candidate, target_item)
                lost_ref = candidate
                found_ref = target_item
            else:
                continue

            if eval_res and eval_res['score'] >= min_threshold:
                results.append({
                    "score": eval_res['score'],
                    "label": eval_res['label'],
                    "badge_class": eval_res['badge_class'],
                    "factors": eval_res['factors'],
                    "lost_item": lost_ref,
                    "found_item": found_ref,
                    "lost_item_id": lost_ref.get('id'),
                    "found_item_id": found_ref.get('id'),
                    "institution_id": target_item.get('institution_id')
                })

        # Rank from highest score to lowest
        results.sort(key=lambda x: x['score'], reverse=True)
        return results
