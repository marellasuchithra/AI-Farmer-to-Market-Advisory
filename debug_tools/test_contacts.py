from geopy.geocoders import Nominatim

def test_nominatim_details():
    geolocator = Nominatim(user_agent="ai_farmer_advisor")
    # Search for "LAVANYA COLD STORAGE" or just "Cold Storage" in a specific area
    # From screenshot: SUBHAMASTHU FUNCTION HALL, LAVANYA COLD STORAGE
    # Let's try to geocode "Lavanya Cold Storage, Andhra Pradesh"
    query = "Lavanya Cold Storage, Andhra Pradesh"
    location = geolocator.geocode(query, exactly_one=False, limit=5, timeout=10, extratags=1)
    
    if location:
        for loc in location:
            print(f"Name: {loc.address}")
            print(f"Raw Tags: {loc.raw.get('extratags', {})}")
            phone = loc.raw.get('extratags', {}).get('phone')
            print(f"Phone: {phone}")
            print("-" * 20)
    else:
        print("No results found.")

if __name__ == "__main__":
    test_nominatim_details()
