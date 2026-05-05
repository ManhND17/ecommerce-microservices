"""
ai_app/services/intent_engine.py — Phân Tích Ý Định Người Dùng (Intent Detection)
===================================================================================
Module rule-based hoàn toàn (không cần model bên ngoài).

Chức năng:
  - detect_intent(query):       Phân tích câu hỏi → trả về intent dict đầy đủ
  - extract_budget(query):      Trích xuất ngân sách (min/max) từ câu hỏi
  - extract_brands(query):      Nhận diện thương hiệu được nhắc đến
  - extract_category(query):    Xác định danh mục sản phẩm
  - extract_comparison(query):  Tìm các sản phẩm/model cần so sánh
  - extract_specs(query):       Xác định thông số kỹ thuật được hỏi

Intent types:
  - price_filter:    "laptop dưới 20 triệu", "điện thoại tầm 10 triệu"
  - brand_filter:    "Samsung Galaxy", "laptop Dell", "iPhone"
  - comparison:      "so sánh A và B", "A hay B tốt hơn"
  - spec_query:      "RAM bao nhiêu", "chip gì", "dung lượng pin"
  - category:        "tìm laptop", "xem điện thoại", "có sách không"
  - recommendation:  "gợi ý cho tôi", "nên mua gì", "tư vấn giúp"
  - greeting:        "xin chào", "hello", "hi"
  - general:         Không xác định được intent cụ thể
"""

import re
from typing import Dict, List, Optional, Tuple


# ── Từ điển thương hiệu ───────────────────────────────────────────────────────

BRANDS: Dict[str, List[str]] = {
    # Laptop
    "apple":   ["macbook", "mac book", "apple mac"],
    "dell":    ["dell", "xps", "inspiron", "latitude", "alienware"],
    "hp":      ["hp", "hewlett packard", "pavilion", "spectre", "omen", "envy"],
    "lenovo":  ["lenovo", "thinkpad", "ideapad", "legion", "yoga"],
    "asus":    ["asus", "vivobook", "zenbook", "rog", "tuf"],
    "acer":    ["acer", "aspire", "nitro", "predator", "swift"],
    "msi":     ["msi", "ms-i"],
    "lg":      ["lg gram", "lg"],
    # Mobile
    "samsung": ["samsung", "galaxy", "s24", "s23", "s22", "note", "a54", "a55"],
    "iphone":  ["iphone", "ios"],
    "xiaomi":  ["xiaomi", "redmi", "poco", "mi "],
    "oppo":    ["oppo", "reno", "find x"],
    "vivo":    ["vivo", "v series"],
    "realme":  ["realme"],
    "nokia":   ["nokia"],
    "oneplus":["oneplus", "one plus"],
    # Generic
    "sony":    ["sony", "xperia", "wh-", "wf-"],
    "jbl":     ["jbl"],
    "logitech":["logitech"],
}

# ── Từ điển danh mục ──────────────────────────────────────────────────────────

CATEGORY_PATTERNS: Dict[str, List[str]] = {
    "laptop": [
        "laptop", "máy tính xách tay", "notebook", "macbook", "ultrabook",
        "gaming laptop", "máy tính", "pc"
    ],
    "mobile": [
        "điện thoại", "smartphone", "iphone", "android", "dt",
        "dien thoai", "phone", "mobile"
    ],
    "books": [
        "sách", "book", "tiểu thuyết", "truyện", "giáo trình",
        "tài liệu", "novel"
    ],
    "clothes": [
        "áo", "quần", "thời trang", "váy", "jacket", "hoodie",
        "tshirt", "t-shirt", "clothes", "fashion", "phụ kiện thời trang"
    ],
    "accessories": [
        "tai nghe", "earphone", "headphone", "chuột", "mouse",
        "bàn phím", "keyboard", "sạc", "cáp", "case", "ốp lưng",
        "pin dự phòng", "powerbank"
    ],
}

# ── Thông số kỹ thuật ─────────────────────────────────────────────────────────

SPEC_PATTERNS: Dict[str, List[str]] = {
    "ram":      ["ram", "bộ nhớ ram", "memory"],
    "storage":  ["ssd", "hdd", "ổ cứng", "lưu trữ", "storage", "dung lượng"],
    "cpu":      ["cpu", "chip", "processor", "vi xử lý", "core i", "ryzen", "snapdragon", "m1", "m2", "m3"],
    "screen":   ["màn hình", "screen", "display", "inch", "hz", "tần số quét", "oled", "ips", "amoled"],
    "battery":  ["pin", "battery", "mah", "thời lượng pin"],
    "camera":   ["camera", "chụp ảnh", "megapixel", "mp", "quay video"],
    "gpu":      ["gpu", "card đồ họa", "vga", "rtx", "gtx", "rx "],
    "weight":   ["trọng lượng", "nặng", "nhẹ", "kg", "gram"],
    "price":    ["giá", "price", "bao nhiêu tiền", "cost", "phí"],
}

# ── Pattern số tiền ───────────────────────────────────────────────────────────

MONEY_PATTERNS = [
    # "dưới 20 triệu", "< 20tr", "dưới 20tr"
    (r"(?:dưới|under|<|nhỏ hơn|không quá|tối đa|max|tầm)\s*(\d+(?:[.,]\d+)?)\s*(?:triệu|tr|million|m\b)", "max"),
    # "trên 5 triệu", "> 5tr"
    (r"(?:trên|trên|>|lớn hơn|từ|from|min|tối thiểu)\s*(\d+(?:[.,]\d+)?)\s*(?:triệu|tr|million|m\b)", "min"),
    # "5-20 triệu", "từ 5 đến 20 triệu"
    (r"(?:từ|from)?\s*(\d+(?:[.,]\d+)?)\s*(?:triệu|tr)?\s*(?:đến|tới|to|-)\s*(\d+(?:[.,]\d+)?)\s*(?:triệu|tr)", "range"),
    # "khoảng 15 triệu", "tầm 15tr"
    (r"(?:khoảng|tầm|around|about|approximately)\s*(\d+(?:[.,]\d+)?)\s*(?:triệu|tr|million|m\b)", "around"),
]

# ── Greeting patterns ─────────────────────────────────────────────────────────

GREETING_PATTERNS = [
    "xin chào", "chào", "hi ", "hello", "hey", "good morning",
    "good afternoon", "chào buổi", "bạn ơi", "cho hỏi", "hỏi chút",
]

# ── Recommendation patterns ───────────────────────────────────────────────────

RECOMMENDATION_PATTERNS = [
    "gợi ý", "recommend", "nên mua", "tư vấn", "chọn giúp",
    "tốt nhất", "phù hợp nhất", "đáng mua", "mua gì", "loại nào",
    "cái nào", "model nào", "sản phẩm nào", "nên chọn",
]

# ── Comparison patterns ───────────────────────────────────────────────────────

COMPARISON_PATTERNS = [
    r"so\s*sánh",
    r"\bvs\b",
    r"hay\s+(?:\w+\s+)?(?:tốt|tốt hơn|hơn|tệ|kém)",
    r"(?:tốt|tốt hơn|hơn|kém)\s+hay",
    r"khác nhau",
    r"nên chọn.+hay",
    r"a hay b",
    r"cái nào tốt hơn",
]


# ══════════════════════════════════════════════════════════════════════════════
# Hàm tiện ích nội bộ
# ══════════════════════════════════════════════════════════════════════════════

def _normalize(text: str) -> str:
    """Chuẩn hóa text: lowercase, loại bỏ dấu câu thừa."""
    return text.lower().strip()


def extract_budget(query: str) -> Dict[str, Optional[float]]:
    """
    Trích xuất ngân sách từ câu hỏi.

    Returns:
        {
            "min": float | None,   # Ngân sách tối thiểu (VNĐ)
            "max": float | None,   # Ngân sách tối đa (VNĐ)
            "around": float | None # Ngân sách xấp xỉ (VNĐ)
        }
    """
    q = _normalize(query)
    result: Dict[str, Optional[float]] = {"min": None, "max": None, "around": None}

    for pattern, budget_type in MONEY_PATTERNS:
        matches = re.findall(pattern, q)
        if not matches:
            continue

        if budget_type == "range" and matches[0] and len(matches[0]) == 2:
            try:
                val_min = float(str(matches[0][0]).replace(",", ".")) * 1_000_000
                val_max = float(str(matches[0][1]).replace(",", ".")) * 1_000_000
                result["min"] = val_min
                result["max"] = val_max
            except (ValueError, TypeError):
                pass
        elif budget_type in ("max", "min", "around") and matches:
            try:
                raw = matches[0] if isinstance(matches[0], str) else str(matches[0])
                val = float(raw.replace(",", ".")) * 1_000_000
                result[budget_type] = val
            except (ValueError, TypeError):
                pass

    return result


def extract_brands(query: str) -> List[str]:
    """
    Nhận diện tất cả thương hiệu được nhắc đến trong query.

    Returns:
        List tên thương hiệu đã chuẩn hóa (ví dụ: ["apple", "dell"])
    """
    q = _normalize(query)
    found: List[str] = []

    for brand_key, keywords in BRANDS.items():
        for kw in keywords:
            if kw in q:
                if brand_key not in found:
                    found.append(brand_key)
                break

    return found


def extract_category(query: str) -> Optional[str]:
    """
    Xác định danh mục sản phẩm từ câu hỏi.

    Returns:
        Tên danh mục (catalog_slug) hoặc None nếu không xác định được.
    """
    q = _normalize(query)
    # Ưu tiên theo thứ tự cụ thể hơn trước
    priority = ["accessories", "mobile", "laptop", "books", "clothes"]
    for cat in priority:
        for kw in CATEGORY_PATTERNS[cat]:
            if kw in q:
                return cat
    return None


def extract_specs_requested(query: str) -> List[str]:
    """
    Xác định thông số kỹ thuật nào đang được hỏi.

    Returns:
        List tên spec (ví dụ: ["ram", "cpu", "screen"])
    """
    q = _normalize(query)
    found: List[str] = []
    for spec_key, keywords in SPEC_PATTERNS.items():
        for kw in keywords:
            if kw in q:
                if spec_key not in found:
                    found.append(spec_key)
                break
    return found


def extract_comparison_targets(query: str) -> List[str]:
    """
    Tìm các model/sản phẩm cụ thể cần so sánh.

    Returns:
        List tên sản phẩm/model (ví dụ: ["MacBook Air", "Dell XPS 13"])
    """
    q = query.strip()
    targets: List[str] = []

    # Pattern: "so sánh A và B" / "A vs B" / "A hay B"
    patterns = [
        r"so\s*sánh\s+(.+?)\s+(?:và|với|vs\.?|&)\s+(.+?)(?:\s*\?|$)",
        r"(.+?)\s+(?:vs\.?|versus)\s+(.+?)(?:\s*\?|$)",
        r"(.+?)\s+hay\s+(.+?)\s+(?:tốt hơn|hơn|tốt|nên mua|đáng mua)(?:\s*\?|$)",
    ]

    for pat in patterns:
        m = re.search(pat, q, re.IGNORECASE)
        if m:
            targets = [g.strip() for g in m.groups() if g and len(g.strip()) > 1]
            if targets:
                break

    return targets


# ══════════════════════════════════════════════════════════════════════════════
# Hàm chính: detect_intent
# ══════════════════════════════════════════════════════════════════════════════

def detect_intent(query: str) -> Dict:
    """
    Phân tích ý định người dùng từ câu hỏi tự nhiên.

    Args:
        query: Câu hỏi của người dùng.

    Returns:
        dict với các key:
          - intent (str):              Loại ý định chính
          - budget (dict):             {"min", "max", "around"} — giá trị VNĐ
          - brands (list[str]):        Thương hiệu được nhắc
          - category (str|None):       Danh mục sản phẩm
          - specs_requested (list):    Thông số kỹ thuật được hỏi
          - comparison_targets (list): Sản phẩm/model cần so sánh
          - confidence (float):        Độ tin cậy phân loại [0, 1]
          - raw_query (str):           Query gốc
    """
    q_lower = _normalize(query)

    # Trích xuất các thực thể
    budget            = extract_budget(query)
    brands            = extract_brands(query)
    category          = extract_category(query)
    specs_requested   = extract_specs_requested(query)
    comparison_targets = extract_comparison_targets(query)

    has_budget  = any(v is not None for v in budget.values())
    has_brand   = bool(brands)
    has_category = category is not None
    has_specs   = bool(specs_requested)
    has_comparison = bool(comparison_targets)

    # ── Phân loại intent theo ưu tiên ────────────────────────────────────────

    # 1. Greeting
    if any(q_lower.startswith(g) or q_lower == g.strip() for g in GREETING_PATTERNS):
        return _build_result("greeting", budget, brands, category,
                             specs_requested, comparison_targets, 0.95, query)

    # 2. Comparison
    if has_comparison or any(re.search(p, q_lower) for p in COMPARISON_PATTERNS):
        return _build_result("comparison", budget, brands, category,
                             specs_requested, comparison_targets, 0.9, query)

    # 3. Spec query — hỏi cụ thể về thông số
    if has_specs and not has_budget:
        spec_questions = ["bao nhiêu", "như thế nào", "thế nào", "mấy", "có không", "tốt không"]
        if any(sq in q_lower for sq in spec_questions):
            return _build_result("spec_query", budget, brands, category,
                                 specs_requested, comparison_targets, 0.85, query)

    # 4. Price filter — có ngân sách cụ thể
    if has_budget:
        return _build_result("price_filter", budget, brands, category,
                             specs_requested, comparison_targets, 0.9, query)

    # 5. Brand filter — hỏi theo thương hiệu
    if has_brand and not has_budget:
        return _build_result("brand_filter", budget, brands, category,
                             specs_requested, comparison_targets, 0.8, query)

    # 6. Recommendation — muốn được gợi ý
    if any(p in q_lower for p in RECOMMENDATION_PATTERNS):
        return _build_result("recommendation", budget, brands, category,
                             specs_requested, comparison_targets, 0.8, query)

    # 7. Category browse — duyệt theo danh mục
    if has_category:
        return _build_result("category", budget, brands, category,
                             specs_requested, comparison_targets, 0.75, query)

    # 8. General — không xác định
    return _build_result("general", budget, brands, category,
                         specs_requested, comparison_targets, 0.4, query)


def _build_result(
    intent: str,
    budget: dict,
    brands: List[str],
    category: Optional[str],
    specs: List[str],
    comparison: List[str],
    confidence: float,
    raw_query: str,
) -> Dict:
    """Helper tạo dict kết quả thống nhất."""
    return {
        "intent":              intent,
        "budget":              budget,
        "brands":              brands,
        "category":            category,
        "specs_requested":     specs,
        "comparison_targets":  comparison,
        "confidence":          confidence,
        "raw_query":           raw_query,
    }


# ══════════════════════════════════════════════════════════════════════════════
# Tiện ích: Format ngân sách thành text
# ══════════════════════════════════════════════════════════════════════════════

def format_budget_text(budget: dict) -> str:
    """Chuyển dict ngân sách thành chuỗi mô tả tiếng Việt."""
    mn, mx, ar = budget.get("min"), budget.get("max"), budget.get("around")

    if mn and mx:
        return f"từ {mn/1e6:.0f} đến {mx/1e6:.0f} triệu"
    elif mx:
        return f"dưới {mx/1e6:.0f} triệu"
    elif mn:
        return f"trên {mn/1e6:.0f} triệu"
    elif ar:
        return f"khoảng {ar/1e6:.0f} triệu"
    return ""


def filter_by_budget(products: List[dict], budget: dict) -> List[dict]:
    """
    Lọc danh sách sản phẩm theo ngân sách.

    Args:
        products: Danh sách sản phẩm, mỗi item có key 'price'.
        budget:   Dict {"min", "max", "around"} — giá trị VNĐ.

    Returns:
        Danh sách sản phẩm đã lọc, sắp xếp theo giá tăng dần.
    """
    mn   = budget.get("min")
    mx   = budget.get("max")
    ar   = budget.get("around")
    tol  = 0.2  # ±20% tolerance cho "khoảng"

    filtered: List[dict] = []
    for p in products:
        try:
            price = float(str(p.get("price", 0)).replace(",", "").replace(".", ""))
        except (ValueError, TypeError):
            price = 0.0

        if price <= 0:
            # Không có giá → giữ lại (không thể lọc)
            filtered.append(p)
            continue

        if ar:
            if ar * (1 - tol) <= price <= ar * (1 + tol):
                filtered.append(p)
        elif mn and mx:
            if mn <= price <= mx:
                filtered.append(p)
        elif mx and price <= mx:
            filtered.append(p)
        elif mn and price >= mn:
            filtered.append(p)
        else:
            filtered.append(p)

    # Sắp xếp theo giá tăng dần
    def _price_sort(p: dict) -> float:
        try:
            return float(str(p.get("price", 0)).replace(",", "").replace(".", ""))
        except (ValueError, TypeError):
            return 0.0

    return sorted(filtered, key=_price_sort)
