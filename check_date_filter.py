
import requests
import json
from datetime import datetime, timedelta

API_KEY = "579b464db66ec23bdd000001aa47c0d689cf49e9715ec1e92efbc941"  # From utils/price_api.py
URL = "https://api.data.gov.in/resource/9ef84268-d588-465a-a308-a864a43d0070"

def check_filters():
    # Use yesterday or day before
    target_date = "15/02/2026"  # Try exact format often used in India
    crop = "Tomato"
    state = "Andhra Pradesh"
    
    print(f"Checking {target_date}...")
    
    params = {
        "api-key": API_KEY,
        "format": "json",
        "filters[commodity]": crop,
        "filters[state]": state,
        "filters[arrival_date]": target_date,
        "limit": 5
    }
    
    try:
        r = requests.get(URL, params=params, timeout=15)
        data = r.json()
        
        if "records" in data:
            recs = data["records"]
            print(f"Matched {len(recs)} records for {target_date}")
            for r in recs:
                print(r.get("arrival_date"), r.get("modal_price"))
        else:
            print("No records found via date filter.")
            print(data)
            
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    check_filters()
