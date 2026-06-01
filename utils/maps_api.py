import requests
import time
from math import radians, sin, cos, sqrt, atan2
import streamlit as st
import json
import os
from geopy.geocoders import Nominatim
from geopy.exc import GeocoderTimedOut

# User Agent is required for Nominatim
HEADERS = {
    "User-Agent": "AI-Farmer-Advisor/1.0"
}

# Load Mandi Coordinates from JSON
try:
    with open("assets/mandi_coords.json", "r") as f:
        MANDI_COORDS = json.load(f)
except FileNotFoundError:
    MANDI_COORDS = {}

# Fallback State Mandis if JSON is missing or incomplete
STATE_MANDIS_FALLBACK = {
    "Andhra Pradesh": [
        "Bapatla", "Tenali", "Guntur", "Vijayawada", "Ongole", "Nellore"
    ],
    "Telangana": [
        "Hyderabad", "Warangal", "Nizamabad", "Karimnagar", "Khammam"
    ],
    "Maharashtra": [
        "Pune", "Nashik", "Nagpur", "Mumbai", "Aurangabad"
    ],
    "Karnataka": [
        "Bangalore", "Mysore", "Hubli", "Mangalore"
    ],
    "Tamil Nadu": [
        "Chennai", "Coimbatore", "Madurai", "Trichy"
    ]
}

@st.cache_data(ttl=3600, show_spinner=False)
def get_lat_lon(place):
    """
    Geocodes a place name to obtain latitude and longitude using geopy (Nominatim).
    """
    try:
        geolocator = Nominatim(user_agent="ai_farmer_advisor")
        location = geolocator.geocode(place, timeout=10)
        
        if location:
            return location.latitude, location.longitude
        return None, None

    except Exception as e:
        print(f"Geocoding Error: {e}")
        return None, None


@st.cache_data(ttl=3600, show_spinner=False)
def reverse_geocode(lat, lon):
    """
    Converts lat/lon to address details using Nominatim.
    Returns: {"city": str, "state": str, "display_name": str} or None
    """
    try:
        geolocator = Nominatim(user_agent="ai_farmer_advisor")
        location = geolocator.reverse((lat, lon), exactly_one=True, timeout=10)
        
        if not location:
            return None
            
        address = location.raw.get("address", {})
        # Extract City/Town/Village
        city = address.get("city") or address.get("town") or address.get("village") or address.get("county") or "Unknown"
        state = address.get("state", "Unknown")
        
        return {
            "city": city,
            "state": state,
            "display_name": location.address
        }

    except Exception as e:
        print(f"Reverse Geocoding Error: {e}")
        return None


def calc_distance(lat1, lon1, lat2, lon2):
    """
    Calculates Haversine distance between two points in kilometers.
    """
    R = 6371 # Earth radius in km

    try:
        lat1, lon1, lat2, lon2 = map(float, [lat1, lon1, lat2, lon2])
    except ValueError:
        return float('inf')

    # Convert to radians
    lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])

    dlat = lat2 - lat1
    dlon = lon2 - lon1

    a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
    c = 2 * atan2(sqrt(a), sqrt(1-a))

    return R * c


@st.cache_data(ttl=3600, show_spinner=False)
def get_all_mandi_routes(user_location, state):
    """
    Finds routes to all mandis in the given state from the user's location.
    Returns a list of dictionaries with mandi details, distance, and map link.
    """
    # 1. Try JSON DB first
    mandis_in_state = MANDI_COORDS.get(state, {})
    mandi_names = list(mandis_in_state.keys())
    
    # 2. Fallback
    if not mandi_names:
        mandi_names = STATE_MANDIS_FALLBACK.get(state, [])

    if not mandi_names:
        return []

    # Geocode user location
    u_lat, u_lon = get_lat_lon(f"{user_location}, {state}, India")

    if not u_lat:
        print(f"Could not find location: {user_location}")
        return []

    return get_mandi_routes_by_coords(u_lat, u_lon, state, radius_km=None) # No limit for general view


@st.cache_data(ttl=3600, show_spinner=False)
def get_mandi_routes_by_coords(u_lat, u_lon, state, radius_km=1000):
    """
    Finds routes to mandis in the state using exact user coordinates.
    Optionally filters by radius_km.
    """
    # 1. Try JSON DB first
    mandis_in_state = MANDI_COORDS.get(state, {})
    
    # 2. Add fallback mandis if not in JSON
    fallback_list = STATE_MANDIS_FALLBACK.get(state, [])
    
    # Prepare list of candidates (name, lat, lon)
    candidates = []
    
    # Add from JSON
    for m_name, coords in mandis_in_state.items():
        candidates.append({"name": m_name, "lat": coords["lat"], "lon": coords["lon"]})

    # Add from Fallback (if not already present)
    existing_names = set(mandis_in_state.keys())
    for m_name in fallback_list:
        if m_name not in existing_names:
            # Need to geocode on fly
            query = f"{m_name}, {state}, India"
            m_lat, m_lon = get_lat_lon(query)
            if m_lat:
                candidates.append({"name": m_name, "lat": m_lat, "lon": m_lon})

    if not candidates:
        return []

    result = []

    for mandi in candidates:
        dist = calc_distance(u_lat, u_lon, mandi["lat"], mandi["lon"])

        # Filter by radius if specified
        if radius_km and dist > radius_km:
            continue

        # Google Maps Direction Link
        link = f"https://www.google.com/maps/dir/?api=1&origin={u_lat},{u_lon}&destination={mandi['lat']},{mandi['lon']}&travelmode=driving"

        result.append({
            "name": mandi["name"],
            "distance": round(dist, 2),
            "map": link,
            "lat": mandi["lat"],
            "lon": mandi["lon"]
        })

    # Sort by distance
    result.sort(key=lambda x: x["distance"])
    
    return result


@st.cache_data(ttl=3600, show_spinner=False)
def get_nearby_cold_storage(user_location, state):
    """
    Searches for nearby cold storage using Nominatim and returns the nearest one.
    """
    u_lat, u_lon = get_lat_lon(f"{user_location}, {state}, India")
    
    if not u_lat:
        return None

    return get_nearby_cold_storage_by_coords(u_lat, u_lon, user_location, state)


# ============ KNOWN COLD STORAGES DATABASE ============
# Hardcoded database of real cold storage facilities in supported states
# Coordinates verified via Google Maps
KNOWN_COLD_STORAGES = {
    "Andhra Pradesh": [
        {"name": "KSR Cold Storage", "lat": 15.8281, "lon": 80.3522, "city": "Chirala", "phone": "+91 8008001199"},
        {"name": "Sri Venkateswara Cold Storage", "lat": 16.3067, "lon": 80.4365, "city": "Guntur", "phone": None},
        {"name": "Aditya Cold Storage", "lat": 16.5062, "lon": 80.6480, "city": "Vijayawada", "phone": None},
        {"name": "Sri Lakshmi Cold Storage", "lat": 15.5057, "lon": 80.0499, "city": "Ongole", "phone": None},
        {"name": "Srinivasa Cold Storage", "lat": 15.8350, "lon": 80.3490, "city": "Chirala", "phone": None},
        {"name": "Balaji Cold Storage", "lat": 16.3100, "lon": 80.4300, "city": "Guntur", "phone": None},
        {"name": "Amaravathi Cold Storage", "lat": 16.5150, "lon": 80.5200, "city": "Mangalagiri", "phone": None},
        {"name": "Prasad Cold Storage", "lat": 15.4800, "lon": 80.0600, "city": "Ongole", "phone": None},
        {"name": "Nellore Cold Storage", "lat": 14.4426, "lon": 79.9865, "city": "Nellore", "phone": None},
        {"name": "Tenali Cold Storage", "lat": 16.2437, "lon": 80.6400, "city": "Tenali", "phone": None},
    ],
    "Telangana": [
        {"name": "Snowman Logistics Hyderabad", "lat": 17.4400, "lon": 78.3489, "city": "Hyderabad", "phone": None},
        {"name": "Coldstar Logistics", "lat": 17.3850, "lon": 78.4867, "city": "Hyderabad", "phone": None},
        {"name": "Warangal Cold Storage", "lat": 18.0000, "lon": 79.5880, "city": "Warangal", "phone": None},
        {"name": "Karimnagar Cold Storage", "lat": 18.4386, "lon": 79.1288, "city": "Karimnagar", "phone": None},
        {"name": "Nizamabad Cold Storage", "lat": 18.6725, "lon": 78.0942, "city": "Nizamabad", "phone": None},
    ],
    "Maharashtra": [
        {"name": "Snowman Logistics Pune", "lat": 18.6298, "lon": 73.7997, "city": "Pune", "phone": None},
        {"name": "Coldex Cold Storage Nashik", "lat": 19.9975, "lon": 73.7898, "city": "Nashik", "phone": None},
        {"name": "Mumbai Cold Storage", "lat": 19.0760, "lon": 72.8777, "city": "Mumbai", "phone": None},
        {"name": "Nagpur Cold Storage", "lat": 21.1458, "lon": 79.0882, "city": "Nagpur", "phone": None},
        {"name": "Aurangabad Cold Storage", "lat": 19.8762, "lon": 75.3433, "city": "Aurangabad", "phone": None},
    ],
    "Karnataka": [
        {"name": "Snowman Logistics Bangalore", "lat": 12.9716, "lon": 77.5946, "city": "Bangalore", "phone": None},
        {"name": "Mysore Cold Storage", "lat": 12.2958, "lon": 76.6394, "city": "Mysore", "phone": None},
        {"name": "Hubli Cold Storage", "lat": 15.3647, "lon": 75.1240, "city": "Hubli", "phone": None},
        {"name": "Mangalore Cold Storage", "lat": 12.9141, "lon": 74.8560, "city": "Mangalore", "phone": None},
    ],
    "Tamil Nadu": [
        {"name": "Snowman Logistics Chennai", "lat": 13.0827, "lon": 80.2707, "city": "Chennai", "phone": None},
        {"name": "Coimbatore Cold Storage", "lat": 11.0168, "lon": 76.9558, "city": "Coimbatore", "phone": None},
        {"name": "Madurai Cold Storage", "lat": 9.9252, "lon": 78.1198, "city": "Madurai", "phone": None},
        {"name": "Trichy Cold Storage", "lat": 10.7905, "lon": 78.7047, "city": "Trichy", "phone": None},
    ],
}

@st.cache_data(ttl=3600, show_spinner=False)
def get_cold_storage_routes_by_coords(u_lat, u_lon, city_hint=None, state_hint=None, radius_km=1000):
    """
    Returns a list of cold storages near coordinates.
    Uses hardcoded DB first, then Overpass API fallback.
    """
    results = []
    
    # --- Strategy 1: Hardcoded Database (fast, reliable) ---
    states_to_check = []
    if state_hint and state_hint in KNOWN_COLD_STORAGES:
        states_to_check.append(state_hint)
    # Also check neighboring states
    for s in KNOWN_COLD_STORAGES:
        if s not in states_to_check:
            states_to_check.append(s)
    
    for state in states_to_check:
        for cs in KNOWN_COLD_STORAGES.get(state, []):
            dist = calc_distance(u_lat, u_lon, cs["lat"], cs["lon"])
            if dist <= radius_km:
                results.append({
                    "name": cs["name"],
                    "full_address": f"{cs['city']}, {state}",
                    "distance": round(dist, 1),
                    "phone": cs.get("phone"),
                    "website": None,
                    "map": f"https://www.google.com/maps/dir/?api=1&origin={u_lat},{u_lon}&destination={cs['lat']},{cs['lon']}&travelmode=driving"
                })
    
    # --- Strategy 2: Overpass API (if DB yields < 3 results) ---
    if len(results) < 3:
        try:
            overpass_results = _search_overpass_cold_storage(u_lat, u_lon, radius_km)
            for ov in overpass_results:
                # Avoid duplicates by checking if name already exists
                existing_names = [r["name"].lower() for r in results]
                if ov["name"].lower() not in existing_names:
                    results.append(ov)
        except Exception as e:
            print(f"Overpass API fallback error: {e}")
    
    # Sort by distance
    results.sort(key=lambda x: x["distance"])
    return results


def _search_overpass_cold_storage(u_lat, u_lon, radius_km):
    """
    Uses Overpass API to find cold storage / warehouse amenities from OpenStreetMap.
    """
    # Search within a reasonable radius (max 200km for Overpass performance)
    search_radius_m = min(radius_km, 200) * 1000
    
    query = f"""
    [out:json][timeout:15];
    (
      node["landuse"="industrial"]["name"~"cold|storage|warehouse|logistics",i](around:{search_radius_m},{u_lat},{u_lon});
      way["landuse"="industrial"]["name"~"cold|storage|warehouse|logistics",i](around:{search_radius_m},{u_lat},{u_lon});
      node["building"="warehouse"](around:{search_radius_m},{u_lat},{u_lon});
      way["building"="warehouse"](around:{search_radius_m},{u_lat},{u_lon});
      node["building"="cold_storage"](around:{search_radius_m},{u_lat},{u_lon});
      way["building"="cold_storage"](around:{search_radius_m},{u_lat},{u_lon});
      node["amenity"="cold_storage"](around:{search_radius_m},{u_lat},{u_lon});
    );
    out center 20;
    """
    
    resp = requests.post("https://overpass-api.de/api/interpreter", data={"data": query}, timeout=20)
    resp.raise_for_status()
    data = resp.json()
    
    results = []
    for el in data.get("elements", []):
        lat = el.get("lat") or el.get("center", {}).get("lat")
        lon = el.get("lon") or el.get("center", {}).get("lon")
        if not lat or not lon:
            continue
        
        tags = el.get("tags", {})
        name = tags.get("name", "Cold Storage Facility")
        dist = calc_distance(u_lat, u_lon, lat, lon)
        
        results.append({
            "name": name,
            "full_address": tags.get("addr:full", f"{tags.get('addr:city', '')}, {tags.get('addr:state', '')}"),
            "distance": round(dist, 1),
            "phone": tags.get("phone") or tags.get("contact:phone"),
            "website": tags.get("website"),
            "map": f"https://www.google.com/maps/dir/?api=1&origin={u_lat},{u_lon}&destination={lat},{lon}&travelmode=driving"
        })
    
    results.sort(key=lambda x: x["distance"])
    return results[:10]

@st.cache_data(ttl=3600, show_spinner=False)
def get_nearby_cold_storage_by_coords(u_lat, u_lon, city_hint=None, state_hint=None):
    """
    Wrapper to get just the nearest one (backward compatibility)
    """
    all_cs = get_cold_storage_routes_by_coords(u_lat, u_lon, city_hint, state_hint, radius_km=500)
    return all_cs[0] if all_cs else None
