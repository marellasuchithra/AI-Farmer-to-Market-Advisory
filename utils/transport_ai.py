"""
AI-based Transport Cost Estimator.
Estimates realistic transport cost (₹/km) based on crop type, quantity, and vehicle type.
"""

# Crop categories by transport characteristics
CROP_CATEGORIES = {
    # Perishable: Need refrigerated/careful transport → Higher cost
    "perishable": [
        "tomato", "banana", "mango", "grapes", "apple", "orange", "papaya",
        "guava", "pomegranate", "watermelon", "muskmelon", "strawberry",
        "pineapple", "lemon", "lime", "sweet orange", "mousambi",
        "brinjal", "okra", "spinach", "coriander", "cabbage", "cauliflower",
        "green chilli", "capsicum", "cucumber", "bitter gourd", "bottle gourd",
        "ridge gourd", "drumstick", "beans", "peas", "mushroom", "lettuce"
    ],
    # Medium: Standard transport, moderate care
    "medium": [
        "potato", "onion", "carrot", "beetroot", "radish", "turnip",
        "garlic", "ginger", "turmeric", "chilly", "red chilli", "dry chilli",
        "tamarind", "coconut", "groundnut", "soyabean", "sunflower",
        "cotton", "sugarcane", "maize", "jowar", "bajra", "ragi",
        "bengal gram", "green gram", "black gram", "red gram", "horse gram",
        "lentil", "tur", "urad", "moong", "masoor", "arhar"
    ],
    # Heavy/bulk: Large quantities, cheaper per unit
    "heavy": [
        "rice", "wheat", "paddy", "jute", "tobacco", "copra",
        "arecanut", "cashewnut", "rubber", "pepper", "cardamom",
        "cinnamon", "clove", "nutmeg", "coffee", "tea"
    ]
}

# Base rates (₹/km) for each category
BASE_RATES = {
    "perishable": 3.5,   # Higher due to perishable nature, needs careful handling
    "medium": 2.5,       # Standard transport
    "heavy": 2.0         # Bulk-friendly, lower per-km cost
}

# Quantity tier multipliers (larger loads = lower per-unit cost, but total cost increases)
# These adjust the ₹/km rate based on how much crop is being transported
QTY_TIERS = [
    (50,    1.3,  "Small load (<50 kg) — higher rate due to inefficient vehicle use"),
    (200,   1.0,  "Medium load (50-200 kg) — standard rate"),
    (500,   0.85, "Large load (200-500 kg) — bulk discount applies"),
    (1000,  0.7,  "Very large load (500-1000 kg) — significant bulk savings"),
    (99999, 0.6,  "Truck load (>1000 kg) — maximum bulk efficiency"),
]

def _get_crop_category(crop_name):
    """Determine the transport category for a crop."""
    crop_lower = crop_name.strip().lower()
    for category, crops in CROP_CATEGORIES.items():
        if crop_lower in crops:
            return category
        # Fuzzy partial match
        for c in crops:
            if c in crop_lower or crop_lower in c:
                return category
    return "medium"  # Default

def _get_qty_tier(qty_kg):
    """Get the quantity multiplier and reasoning."""
    for max_qty, multiplier, reason in QTY_TIERS:
        if qty_kg <= max_qty:
            return multiplier, reason
    return 0.6, "Truck load — maximum bulk efficiency"

def estimate_transport_rate(crop_name, qty_kg):
    """
    AI-based transport cost estimator.
    
    Args:
        crop_name: Name of the crop
        qty_kg: Quantity in kilograms
    
    Returns:
        dict with:
            - rate_per_km: Estimated ₹/km for the total load
            - rate_per_km_per_kg: Rate per km per kg
            - category: Crop transport category
            - reasoning: Human-readable explanation
    """
    category = _get_crop_category(crop_name)
    base_rate = BASE_RATES[category]
    qty_multiplier, qty_reason = _get_qty_tier(qty_kg)
    
    # Final rate = base_rate × qty_multiplier
    # This is the rate per km for the ENTIRE load
    rate_per_km = round(base_rate * qty_multiplier, 2)
    
    # Per kg per km rate (for breakdown)
    rate_per_km_per_kg = round(rate_per_km / max(qty_kg, 1), 4) if qty_kg > 0 else rate_per_km
    
    # Build reasoning
    category_labels = {
        "perishable": "🥬 Perishable crop — needs careful/quick transport",
        "medium": "🧅 Standard crop — regular transport",
        "heavy": "🌾 Bulk/heavy crop — efficient bulk transport"
    }
    
    reasoning = (
        f"{category_labels.get(category, 'Standard crop')}. "
        f"{qty_reason}. "
        f"Estimated rate: ₹{rate_per_km}/km for {qty_kg} kg."
    )
    
    return {
        "rate_per_km": rate_per_km,
        "rate_per_km_per_kg": rate_per_km_per_kg,
        "category": category,
        "reasoning": reasoning
    }
