def transport_cost(distance, rate=3.0):
    """
    Calculates transport cost based on distance and rate per km for the whole load.
    Rate (₹/km) already accounts for crop type and quantity.
    """
    return round(distance * rate, 2)


def calc_profit(price, qty, cost, distance, transport_rate=3.0):
    """
    Calculates net profit.
    Profit = (Price * Qty) - Cultivation Cost - Transport Cost
    Transport Cost = distance * rate_per_km (rate is for the whole load)
    """
    transport = transport_cost(distance, transport_rate)
    total = price * qty
    profit = total - cost - transport
    return profit, transport


def best_mandi_profit(mandis, price_data, qty, cost, transport_rate=3.0):
    """
    Finds the mandi that yields the highest profit.
    price_data: Can be a float (legacy) or dict ({"average": float, "markets": {name: price}})
    transport_rate: ₹/km for the whole load (already accounts for crop type and quantity)
    """
    if not mandis:
        return None

    best = None
    
    # Handle legacy float price
    default_price = price_data if isinstance(price_data, (int, float)) else price_data.get("average", 0)
    market_prices = price_data.get("markets", {}) if isinstance(price_data, dict) else {}

    for m in mandis:
        # Determine price for this specific mandi
        m_name = m["name"].title()
        current_price = default_price
        
        # Try to find specific price
        if m_name in market_prices:
            current_price = market_prices[m_name]
        else:
            # Simple substring match fallback
            for k, v in market_prices.items():
                if m_name in k or k in m_name:
                    current_price = v
                    break
        
        profit, transport = calc_profit(
            current_price, qty, cost, m["distance"], transport_rate
        )

        if not best or profit > best["profit"]:
            best = {
                "mandi": m["name"],
                "distance": m["distance"],
                "map": m["map"],
                "profit": profit,
                "transport": transport,
                "price": current_price,
                "net_profit": profit
            }

    return best



# Approximate Shelf Life in Days (assuming standard conditions)
SHELF_LIFE = {
    "tomato": 10,
    "potato": 60,
    "onion": 90,
    "chilly": 20,
    "brinjal": 7,
    "okra": 5,
    "carrot": 15,
    "cabbage": 14,
    "mango": 10,
    "banana": 5
}

def get_shelf_life(crop):
    return SHELF_LIFE.get(crop.lower(), 7) # Default 7 days

from utils.transport_ai import CROP_CATEGORIES

def get_volatility(crop):
    """
    Returns estimated daily price volatility/growth based on crop type.
    Simulates market behavior: Perishables rise fast (short supply), grains stable.
    """
    crop_lower = crop.lower()
    for cat, crops in CROP_CATEGORIES.items():
        # Check direct match or partial
        for c in crops:
            if c in crop_lower or crop_lower in c:
                if cat == "perishable": return 0.025  # 2.5% daily (High volatility)
                if cat == "medium": return 0.015      # 1.5% daily
                if cat == "heavy": return 0.005       # 0.5% daily
    return 0.015 # Default

def predict_price(price, days, volatility=0.015):
    """
    Prediction model using dynamic volatility.
    """
    return round(price * (1 + volatility * days), 2)


from datetime import datetime, timedelta

def store_analysis(price, qty, cost, mandis, crop, days_since_harvest=0, transport_rate=3.0, storage_rate=0.01):
    """
    Analyzes profit if crop is stored.
    Finds the optimal number of days to store within the remaining shelf life.
    Returns: best_days, best_date_str, future_price, best_stored_profit, best_mandi_deal, daily_analysis
    """
    base_price = price if isinstance(price, (int, float)) else price.get("average", 0)
    total_life = get_shelf_life(crop)
    remaining_life = max(0, total_life - days_since_harvest)
    
    # AI Feature: Get crop-specific volatility for 'Good Will' prediction
    volatility = get_volatility(crop)
    
    if remaining_life <= 1:
        # Not enough life to store
        return 0, datetime.now().strftime("%d %b %Y"), base_price, 0, None, []

    # Compare including Day 0 (Today)
    best_stored_profit = base_price * qty - cost - (best_mandi_profit(mandis, price, qty, cost, transport_rate)["transport"] if best_mandi_profit(mandis, price, qty, cost, transport_rate) else 0)
    best_days = 0
    best_mandi_deal = best_mandi_profit(mandis, price, qty, cost, transport_rate)
    final_future_price = base_price

    # Check potential profit for each day up to remaining life (capped at 30 days for safety)
    check_range = min(remaining_life, 30)
    
    daily_analysis = []
    
    # Add Today to analysis
    daily_analysis.append({
        "Day": 0,
        "Date": datetime.now().strftime("%d %b"),
        "Profit": int(best_stored_profit),
        "Price": base_price,
        "StorageCost": 0
    })

    for d in range(1, check_range + 1):
        future_base_p = predict_price(base_price, d, volatility)
        
        # Reconstruct a "Future Price Data" object
        future_price_data = future_base_p
        
        if isinstance(price, dict):
            future_markets = {k: predict_price(v, d, volatility) for k, v in price.get("markets", {}).items()}
            future_price_data = {
                "average": future_base_p,
                "markets": future_markets
            }
        
        # Dynamic Storage Cost: storage_rate (default 1%) of current value per day (scales with price)
        storage_cost = storage_rate * base_price * qty * d
        
        # Find best mandi at future price (pass transport_rate through)
        mandi_deal = best_mandi_profit(mandis, future_price_data, qty, cost, transport_rate)
        
        if mandi_deal:
            # Net profit after storage
            net_profit_stored = mandi_deal["profit"] - storage_cost
            
            # Store daily analysis
            day_date = datetime.now() + timedelta(days=d)
            daily_analysis.append({
                "Day": d,
                "Date": day_date.strftime("%d %b"),
                "Profit": int(net_profit_stored),
                "Price": future_base_p,
                "StorageCost": int(storage_cost)
            })
            
            if net_profit_stored > best_stored_profit:
                best_stored_profit = net_profit_stored
                best_days = d
                final_future_price = mandi_deal.get("price", future_base_p)
                best_mandi_deal = mandi_deal

    # Calculate exact date
    best_date = datetime.now() + timedelta(days=best_days)
    best_date_str = best_date.strftime("%d %b %Y")

    return best_days, best_date_str, final_future_price, best_stored_profit, best_mandi_deal, daily_analysis


def compare_profits(current_profit, stored_profit):
    """
    Returns True if stored profit is significantly better (>15% increase).
    """
    if current_profit <= 0:
        return True, 100 # If current is loss, any profit is better
    
    if stored_profit <= current_profit:
        return False, 0
    
    percent_inc = ((stored_profit - current_profit) / abs(current_profit)) * 100
    
    return percent_inc > 15, round(percent_inc, 1)

