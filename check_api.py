
import requests
import json

API_KEY = "579b464db66ec23bdd000001aa47c0d689cf49e9715ec1e92efbc941"  # From utils/price_api.py
URL = "https://api.data.gov.in/resource/9ef84268-d588-465a-a308-a864a43d0070"

def check_history():
    crop = "Tomato"
    state = "Andhra Pradesh"
    
    params = {
        "api-key": API_KEY,
        "format": "json",
        "filters[commodity]": crop,
        "filters[state]": state,
        "limit": 10  # Just get a few to inspect
    }
    
    try:
        r = requests.get(URL, params=params, timeout=10)
        data = r.json()
        
        if "records" in data:
            recs = data["records"]
            print(f"Found {len(recs)} records.")
            if recs:
                print("Sample Record Keys:", recs[0].keys())
                for i, rec in enumerate(recs[:5]):
                    print(f"Rec {i}: Date={rec.get('arrival_date')}, Market={rec.get('market')}, Price={rec.get('modal_price')}")
        else:
            print("No records found or API error.")
            print(data)
            
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    check_history()
