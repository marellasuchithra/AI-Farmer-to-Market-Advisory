# AI Farmer Advisor - Navigation & Cold Storage Analysis
# Version: 1.1.0 - Improved Precise GPS Navigation
import streamlit as st
import os
import pandas as pd
from datetime import datetime

# ================== IMPORTS ==================
from utils.price_api import get_price
from utils.weather_api import get_weather_condition
from utils.maps_api import get_all_mandi_routes, get_nearby_cold_storage, get_mandi_routes_by_coords, get_nearby_cold_storage_by_coords, reverse_geocode
from utils.decision import best_mandi_profit, store_analysis, compare_profits
from utils.db import save_farmer

from utils.voice_out import speak_full, detect_lang
from utils.translator import translate
from models.freshness_model import check_freshness
from models.cv_model import analyze_image, verify_crop_image
from utils.transport_ai import estimate_transport_rate
from utils.localization import get_text
from utils.location import get_live_location
from streamlit_js_eval import get_geolocation

# ================== CONFIG ==================
st.set_page_config(
    page_title="AI Farmer Advisor",
    layout="wide",
    page_icon="🌾"
)

# ================== SESSION STATE INIT ==================
if "lang" not in st.session_state:
    st.session_state.lang = "en"

# Navigation State
if "page" not in st.session_state:
    st.session_state.page = "home"

# Analysis Data Persistence
if "final_crop" not in st.session_state: st.session_state.final_crop = ""
if "final_location" not in st.session_state: st.session_state.final_location = ""
if "final_quantity" not in st.session_state: st.session_state.final_quantity = 1
if "final_cost" not in st.session_state: st.session_state.final_cost = 0
if "final_days" not in st.session_state: st.session_state.final_days = 0
if "analyzed_image" not in st.session_state: st.session_state.analyzed_image = None
# Auto-detect location tracking
if "auto_city" not in st.session_state: st.session_state.auto_city = None
if "coords" not in st.session_state: st.session_state.coords = None
if "geo_ts" not in st.session_state: st.session_state.geo_ts = 0


# Initial Location Check
if "location_init_done" not in st.session_state:
     # Try to fetch live location once on startup
    live_loc = get_live_location()
    if live_loc:
        st.session_state.final_location = live_loc["city"]
        st.session_state.auto_city = live_loc["city"] # Track auto-detected name
        st.session_state.coords = {"lat": live_loc["lat"], "lon": live_loc["lon"]}
        
        # State matching logic
        detected_region = live_loc["region"]
        supported_states = ["Andhra Pradesh", "Telangana", "Maharashtra", "Karnataka", "Tamil Nadu"]
        found_state = None
        
        for s in supported_states:
            if s.lower() in detected_region.lower() or detected_region.lower() in s.lower():
                found_state = s
                break
        
        if not found_state:
             if "Andhra" in detected_region: found_state = "Andhra Pradesh"
             elif "Telangana" in detected_region: found_state = "Telangana"

        if found_state:
             st.session_state.state_idx = supported_states.index(found_state)
             # Update Widget State Directly
             st.session_state.w_state = found_state
             st.session_state.w_location = live_loc["city"]
    else:
        st.session_state.auto_city = None
    
    st.session_state.location_init_done = True 


# ================== SIDEBAR ==================
with st.sidebar:
    st.header(get_text("settings", st.session_state.lang))

    def change_lang():
        st.session_state.lang = st.session_state.lang_select

    st.selectbox(
        get_text("lang_select", st.session_state.lang),
        ["en", "hi", "te", "ta", "kn", "mr"],
        key="lang_select",
        on_change=change_lang
    )

# ================== TITLE ==================
st.markdown(
    f"<h1 style='text-align:center;'>{get_text('title', st.session_state.lang)}</h1>",
    unsafe_allow_html=True
)

# ================== HOME PAGE (INPUT) ==================
if st.session_state.page == "home":
    col1, col2 = st.columns(2)

    with col1:
        st.subheader(get_text("farmer_details", st.session_state.lang))

        supported_states = ["Andhra Pradesh", "Telangana", "Maharashtra", "Karnataka", "Tamil Nadu"]
        s_idx = st.session_state.get("state_idx", 0)

        # Text Input for Crop (Use w_ prefix for widgets to distinguish from persistent Final vars)
        st.text_input(get_text("crop_name", st.session_state.lang), key="w_crop", value=st.session_state.final_crop)
        
        # Location Row with Live Button
        loc_c1, loc_c2 = st.columns([0.7, 0.3])

        # Execute Button Logic FIRST (Right Column)
        with loc_c2:
            st.write("") # Spacer
            st.write("") 
            
            # Browser-based Geolocation Button
            loc_data = get_geolocation(component_key="get_loc")
            
            if loc_data and "coords" in loc_data:
                lat = loc_data["coords"]["latitude"]
                lon = loc_data["coords"]["longitude"]
                timestamp = loc_data.get("timestamp", 0)
                
                # Check if this is a new update to avoid loop
                if timestamp > st.session_state.get("geo_ts", 0):
                    st.session_state.geo_ts = timestamp
                    st.session_state.coords = {"lat": lat, "lon": lon}
                    
                    # Reverse Geocode to get City/State
                    with st.spinner("📍 Found coordinates! Getting address..."):
                        rev = reverse_geocode(lat, lon)
                        
                        if rev:
                            # Update Widget State Indirectly? 
                            # Streamlit widgets obey 'value' only on init. To update programmatically, we set session_state['w_location']
                            st.session_state.w_location = rev["city"]
                            st.session_state.auto_city = rev["city"]
                            
                            # Map State
                            detected_state = rev["state"]
                            found_state = None
                            for s in supported_states:
                                if s.lower() in detected_state.lower() or detected_state.lower() in s.lower():
                                    found_state = s
                                    break
                            
                            if not found_state:
                               if "Andhra" in detected_state: found_state = "Andhra Pradesh"
                               elif "Telangana" in detected_state: found_state = "Telangana"
                            
                            if found_state:
                                st.session_state.state_idx = supported_states.index(found_state)
                                st.session_state.w_state = found_state
                            
                            st.success(f"📍 {rev['city']}, {rev['state']}")
                            st.rerun()
                        else:
                            st.warning("📍 Coords found, but address lookup failed.")
    
        # Render Input Field SECOND (Left Column)
        with loc_c1:
             # Default value comes from persistent state if available
             st.text_input(get_text("location", st.session_state.lang) + " *", key="w_location", value=st.session_state.final_location)
        
        state = st.selectbox(
            get_text("state", st.session_state.lang) + " *",
            supported_states,
            index=s_idx,
            key="w_state" 
        )

        st.number_input(get_text("quantity", st.session_state.lang), min_value=1, key="w_quantity", step=1, value=st.session_state.final_quantity)
        st.number_input(get_text("cost", st.session_state.lang), min_value=0, key="w_cost", step=1, value=st.session_state.final_cost)
        st.number_input(get_text("days", st.session_state.lang), min_value=0, key="w_days", step=1, value=st.session_state.final_days)

    with col2:
        st.subheader(get_text("crop_image", st.session_state.lang))
        
        img_option = st.radio("Input Method", ["Camera", "Upload"], horizontal=True, label_visibility="collapsed")
        
        if img_option == "Camera":
            st.camera_input(get_text("take_photo", st.session_state.lang), key="w_cam_input")
        else:
            st.file_uploader("Upload Image", type=["jpg", "png", "jpeg"], key="w_file_input")

    # ================== ANALYZE BUTTON ==================
    def on_analyze_click():
        # Validation
        if not st.session_state.w_location or not st.session_state.w_state:
            st.session_state.input_error = "📍 Village/City and State are required fields!"
            return

        # Persist inputs
        st.session_state.input_error = None
        st.session_state.final_crop = st.session_state.w_crop
        st.session_state.final_location = st.session_state.w_location
        st.session_state.final_quantity = st.session_state.w_quantity
        st.session_state.final_cost = st.session_state.w_cost
        st.session_state.final_days = st.session_state.w_days
        st.session_state.final_state = st.session_state.w_state
        
        # Persist Image
        img = None
        if st.session_state.get("w_cam_input"):
             img = st.session_state.w_cam_input
        elif st.session_state.get("w_file_input"):
             img = st.session_state.w_file_input
        
        if img:
             st.session_state.analyzed_image = img
        
        # Navigate
        st.session_state.page = "analysis"
        
    if st.session_state.get("input_error"):
        st.error(st.session_state.input_error)
        
    st.button(get_text("analyze", st.session_state.lang), use_container_width=True, on_click=on_analyze_click)


# ================== ANALYSIS PAGE (RESULTS) ==================
elif st.session_state.page == "analysis":
    
    # Back Button
    col_back, col_title = st.columns([0.2, 0.8])
    with col_back:
        def go_home():
            st.session_state.page = "home"
            # Optional: Clear image?
            # st.session_state.analyzed_image = None
        st.button("⬅️ Back to Search", on_click=go_home)

    # Fetch Persistent Data
    crop = st.session_state.final_crop
    location = st.session_state.final_location
    qty = st.session_state.final_quantity
    cost = st.session_state.final_cost
    days = st.session_state.final_days
    state = st.session_state.get("final_state", "Andhra Pradesh") # Default fallback
    image = st.session_state.analyzed_image
    lang = st.session_state.lang

    # ===== EXACT GPS CAPTURE (Browser-based, takes priority over IP) =====
    # Request browser GPS on the analysis page too
    analysis_loc = get_geolocation(component_key="analysis_gps")
    if analysis_loc and "coords" in analysis_loc:
        gps_lat = analysis_loc["coords"]["latitude"]
        gps_lon = analysis_loc["coords"]["longitude"]
        gps_ts = analysis_loc.get("timestamp", 0)
        
        # Only update if newer than what we have
        if gps_ts > st.session_state.get("geo_ts", 0):
            st.session_state.geo_ts = gps_ts
            st.session_state.coords = {"lat": gps_lat, "lon": gps_lon}
            
            # Also reverse-geocode to update city/state if not manually entered
            if location == st.session_state.get("auto_city"):
                rev = reverse_geocode(gps_lat, gps_lon)
                if rev:
                    location = rev["city"]
                    st.session_state.final_location = location
                    st.session_state.auto_city = location

    # Show user which coordinates are being used
    if st.session_state.get("coords"):
        user_lat = st.session_state.coords["lat"]
        user_lon = st.session_state.coords["lon"]
        st.caption(f"📍 **Your coordinates:** {user_lat:.6f}, {user_lon:.6f} — [Verify on Map](https://www.google.com/maps?q={user_lat},{user_lon})")

    if not crop:
        st.error(get_text("error_req", lang))
        # Button to go back
    else:

        # Auto-detect location if not provided
        if not location:
            with st.spinner(get_text("analyzing", lang) + " (Detecting Location...)"):
                loc_data = get_live_location()
                if loc_data:
                    location = loc_data["city"]
                    st.session_state.final_location = location
                    st.session_state.auto_city = location
                    # Only set IP coords if no GPS coords already captured
                    if not st.session_state.get("coords"):
                        st.session_state.coords = {"lat": loc_data["lat"], "lon": loc_data["lon"]}
                    
                    # Update State automatically
                    detected_region = loc_data["region"]
                    supported_states = ["Andhra Pradesh", "Telangana", "Maharashtra", "Karnataka", "Tamil Nadu"]
                    for s in supported_states:
                        if s.lower() in detected_region.lower() or detected_region.lower() in s.lower():
                            state = s
                            st.session_state.state_idx = supported_states.index(s)
                            break
                    
                    st.success(f"📍 Auto-detected: {location}, {state}")
                else:
                    st.error("Could not detect location. Please enter manually.")
                    st.stop()
    
        with st.spinner(get_text("analyzing", lang)):
        
            freshness, quality = "N/A", "N/A"
            crop_image_match = None
            if image:
                freshness = check_freshness(image, days)
                quality = analyze_image(image)
                
                # Feature 4: Crop image vs name mismatch detection
                # Check seekable
                try:
                    image.seek(0)  # Reset stream before verification
                    crop_image_match = verify_crop_image(image, crop)
                    image.seek(0)  # Reset again for any downstream use
                except:
                    pass # Image might not be seekable depending on type
    
            # Get full price data (Average + Per Market)
            from utils.price_api import get_market_prices
            price_data = get_market_prices(crop, state)
            
            # Invalid Crop Handling
            if isinstance(price_data, dict) and "error" in price_data:
                st.error(price_data["error"])
                st.stop()
            
            if price_data is None:
                 st.error(f"⚠️ Could not fetch market price for '{crop}' in '{state}'. Please check the crop name or try a generic name (e.g., 'Tomato' instead of 'Tomato Hybrid').")
                 st.stop()
    
            # Extract average for display default
            avg_price = price_data.get("average", 0)
            resolved_crop = price_data.get("crop_name", crop)
            
            # Display resolved crop name if fuzzy matched
            if resolved_crop.lower() != crop.lower():
                st.info(f"ℹ️ **Note:** Searched for '**{resolved_crop}**' instead of '{crop}'.")
                crop = resolved_crop # Update crop name for downstream logic
    
            # Location Logic: STRICT MANUAL PRIORITY
            target_lat, target_lon = None, None
            route_origin_lat, route_origin_lon = None, None  # For Google Maps origin
            
            # Check if manual input differs from auto-detected city
            is_manual = location != st.session_state.get("auto_city")
            
            from utils.maps_api import get_lat_lon, get_mandi_routes_by_coords, get_all_mandi_routes, get_nearby_cold_storage_by_coords
            
            # ALWAYS use session coords (GPS/IP) as the true route origin for navigation
            if st.session_state.get("coords"):
                route_origin_lat = st.session_state.coords["lat"]
                route_origin_lon = st.session_state.coords["lon"]
            
            if is_manual:
                 # Force geocode new location — get coords for the entered city
                 geo_lat, geo_lon = get_lat_lon(f"{location}, {state}, India")
                 if geo_lat:
                     target_lat, target_lon = geo_lat, geo_lon
                     # If no GPS/IP coords, use geocoded coords as route origin too
                     if not route_origin_lat:
                         route_origin_lat, route_origin_lon = geo_lat, geo_lon
                 else:
                     target_lat = None # Geocoding failed
            else:
                 # Use stored coords if available (GPS/IP based)
                 if st.session_state.get("coords"):
                     target_lat = st.session_state.coords["lat"]
                     target_lon = st.session_state.coords["lon"]
            
            # Mandi/Coord Logic
            mandis = []
            best = None
            has_location_coords = False
            
            if target_lat:
                 has_location_coords = True
                 mandis = get_mandi_routes_by_coords(target_lat, target_lon, state)
            else:
                 # Geocoding failed or no coords. 
                 if is_manual:
                     st.warning(f"⚠️ Could not pinpoint exact location for '**{location}**'. Distance calculations and Map links will be disabled.")
                 
                 # Fallback: Just proceed with NO mandis found for distance logic, but we still have Prices.
            
            if has_location_coords and not mandis:
                st.warning(f"No mandis found within {state} for the given location.")
    
            # Feature 3: AI-based Transport Cost Estimation (Run early for profit calc)
            # Default rate if AI fails or not run
            ai_rate_val = 3.0 
            ai_transport = {"rate_per_km": 3.0, "reasoning": "Default rate (AI pending)"}
            
            if crop and qty > 0:
                ai_transport = estimate_transport_rate(crop, qty)
                ai_rate_val = float(ai_transport["rate_per_km"])
    
            if mandis:
                # Pass AI-estimated rate to profit calculation
                best = best_mandi_profit(mandis, price_data, qty, cost, transport_rate=ai_rate_val)
                weather = get_weather_condition(best["mandi"]) if best else "Unknown"
            else:
                 best = None
                 weather = "Unknown"
    
            # Get storage rate from session state or default
            storage_rate_pct = st.session_state.get("w_storage_rate", 1.0)
            storage_rate_val = storage_rate_pct / 100.0

            # Check Cold Storage option
            # Pass AI-estimated rate and user storage rate to storage analysis
            rec_days, rec_date, future_price, stored_profit, best_stored, profit_roadmap = store_analysis(
                price_data, qty, cost, mandis, crop, days, transport_rate=ai_rate_val, storage_rate=storage_rate_val
            )
            
            should_store, profit_inc = compare_profits(best["profit"] if best else 0, stored_profit)
            
            decision = "STORE" if should_store else "SELL"
            
            save_farmer(crop, location, qty, cost)
    
        decision_text = f"✅ **Best Strategy:** {'Sell Now' if not should_store else f'Store for {rec_days} days'}"
        st.success(decision_text)
        
        # Display explicit comparison
        sell_profit = int(best['profit']) if best else 0
        if should_store:
            st.info(f"💡 **Why?** Storing until **{rec_date}** increases profit from **₹{sell_profit}** to **₹{int(stored_profit)}** (+{profit_inc}%).")
        else:
            st.info(f"💡 **Why?** Selling now is the best option with a profit of **₹{sell_profit}**.")
        
        # No longer showing image quality or mismatch warnings as requested
        pass
    
        # ================== NEW STRATEGY SECTION ==================
        # Only show if valid location coords were found
        if has_location_coords:
            st.divider()
            st.header(f"🚀 Market Strategy (1000km Radius)")
            
            # Feature 3: AI-based Transport Cost Estimation (Already calculated above)
            # ai_transport = estimate_transport_rate(crop, qty) -> Moved up
            ai_rate = ai_transport["rate_per_km"]
            
            strat_col1, strat_col2 = st.columns(2)
            with strat_col1:
                # AI-estimated transport cost with manual override option
                trans_cost_per_km = st.number_input(
                    f"🚚 Transport Cost (₹/km for {qty}kg)", 
                    min_value=0.0, value=float(ai_rate), step=0.5, format="%.2f",
                    help="AI-estimated rate. You can adjust manually."
                )
            
            with strat_col2:
                # Storage Cost Rate
                st.number_input(
                    "❄️ Storage Rate (% per day)",
                    min_value=0.0, max_value=10.0, value=1.0, step=0.1, key="w_storage_rate",
                    help="Daily cost to store crop in cold storage (as % of current value)."
                )
                st.caption(f"🤖 **Transport AI Estimate:** ₹{ai_rate}/km")
                st.caption(f"{ai_transport['reasoning']}")
    
            # 1. Use the coordinates we resolved earlier (target_lat/lon)
            strat_lat, strat_lon = target_lat, target_lon
                
            # 2. Filter Mandis within 100km
            nearby_mandis = []
            if strat_lat:
                nearby_mandis = get_mandi_routes_by_coords(strat_lat, strat_lon, state, radius_km=1000)
                
                # ALWAYS rebuild map links with user's real coords (GPS/IP) as origin
                if route_origin_lat:
                    for m in nearby_mandis:
                        m["map"] = f"https://www.google.com/maps/dir/?api=1&origin={route_origin_lat},{route_origin_lon}&destination={m['lat']},{m['lon']}&travelmode=driving"
            
            # 3. Calculate Profit for filtered mandis using Custom Transport Cost
            strategy_results = []
            
            market_prices = price_data.get("markets", {}) if isinstance(price_data, dict) else {}
            
            # Fallback price
            base_price = price_data if isinstance(price_data, (int, float)) else price_data.get("average", 0)
    
            if nearby_mandis:
                # Calculate for each nearby mandi
                for m in nearby_mandis:
                    # Determine price (Exact or Average)
                    m_price = base_price
                    m_name = m["name"].title()
                    
                    # Key matching logic
                    if m_name in market_prices:
                         m_price = market_prices[m_name]
                    else:
                         for k, v in market_prices.items():
                            if m_name in k or k in m_name:
                                m_price = v
                                break
                    
                    t_cost = m["distance"] * trans_cost_per_km
                    revenue = m_price * qty
                    net_profit = revenue - cost - t_cost
                    
                    strategy_results.append({
                        "Mandi": m["name"],
                        "Distance (km)": m["distance"],
                        "Price (₹/kg)": m_price,
                        "Transport Cost (₹)": round(t_cost, 1),
                        "Net Profit (₹)": int(net_profit),
                        "Map": m["map"]
                    })
                
                # Sort by Net Profit
                strategy_results.sort(key=lambda x: x["Net Profit (₹)"], reverse=True)
                
                # Display Top 5
                top_5 = strategy_results[:5]
                
                if top_5:
                    # 1. Recommend Best
                    best_strat = top_5[0]
                    st.success(f"🏆 **Best Option:** **{best_strat['Mandi']}** (Profit: ₹{best_strat['Net Profit (₹)']})")
                    
                    # Show calculation breakdown for best option
                    calc_dist = best_strat['Distance (km)']
                    calc_rate = trans_cost_per_km
                    calc_t_cost = best_strat['Transport Cost (₹)']
                    st.caption(f"ℹ️ **Transport Calculation:** {calc_dist} km × ₹{calc_rate}/km = ₹{calc_t_cost}")
                    st.markdown(f"📍 **[Navigate to {best_strat['Mandi']}]({best_strat['Map']})**")
                    
                    # 2. Results shown in expander for cleaner UI
                    with st.expander("📋 View Top 5 Profitable Mandis"):
                        import pandas as pd
                        df_display = pd.DataFrame(top_5).drop(columns=["Map"])
                        st.table(df_display)
                    
                else:
                    st.warning("No profitable mandis found within 1000km.")
                    
        else:
            st.warning("No mandis found within 1000km radius of your location.")
        
        # Fallback View: show Market Prices if NO location found or just as comprehensive info
        if price_data and isinstance(price_data, dict) and "markets" in price_data:
                 with st.expander("📊 View All Market Prices (Statewide)"):
                      st.json(price_data["markets"])
    
    
        # Cold Storage Recommendation - Show Analysis Always if valid days
        if rec_days > 0:
            st.divider()
            st.subheader(f"❄️❄️ {get_text('cold_storage', lang)}")
            
            # Strategy Display
            display_future_price = 0
            try:
                 if isinstance(future_price, (int, float)):
                     display_future_price = future_price
                 elif isinstance(future_price, dict) or hasattr(future_price, "get"):
                     display_future_price = future_price.get("average", 0)
                 else:
                     display_future_price = float(future_price)
            except:
                display_future_price = 0 
    
            if display_future_price and display_future_price != 0 and should_store:
                 # Calculate breakdown
                 if best_stored:
                     storage_cost_total = int(best_stored['profit'] - stored_profit)
                     revenue_future = int(best_stored['price'] * qty)
                     trans_cost_future = int(best_stored['transport'])
                     
                     st.write(f"### ❄️ Storing Breakdown ({rec_days} Days)")
                     st.success(f"""
                     💰 **Net Profit after Storage: ₹{int(stored_profit)}**  
                     - Expected Revenue: ₹{revenue_future}  
                     - Cultivation Cost: -₹{cost}  
                     - Transport Cost: -₹{trans_cost_future}  
                     - **Storage Cost: -₹{storage_cost_total}**  
                     """)
                 else:
                     st.success(f"📌 **Strategy:** Store until **{rec_date}** ({rec_days} days) -> to get approx **₹{display_future_price}/kg**. Est Net Profit: **₹{int(stored_profit)}**")
            elif not should_store:
                 st.info("❄️ Cold storage is available, but selling now is more profitable.")
            else:
                 st.warning(f"⚠️ Strategy data incomplete.")
    
            msg = get_text("cs_msg", lang).format(profit_diff=profit_inc)
            st.write(msg)
            
            # Cold Storage Search (Coords vs Text) - Fetch Top 5
            all_cs = []
            if has_location_coords:
                 # Use the new Viewbox search logic
                 from utils.maps_api import get_cold_storage_routes_by_coords
                 all_cs = get_cold_storage_routes_by_coords(target_lat, target_lon, location, state, radius_km=1000)
                 
                 # ALWAYS rebuild cold storage map links with user's real coords as origin
                 if route_origin_lat:
                     for cs_loc in all_cs:
                         cs_map_parts = cs_loc["map"].split("destination=")
                         if len(cs_map_parts) > 1:
                             cs_dest = cs_map_parts[1].split("&")[0]
                             cs_loc["map"] = f"https://www.google.com/maps/dir/?api=1&origin={route_origin_lat},{route_origin_lon}&destination={cs_dest}&travelmode=driving"
            else:
                 # Fallback to nearest via text search
                 try:
                    from utils.maps_api import get_nearby_cold_storage
                    nearest = get_nearby_cold_storage(location, state)
                    if nearest: all_cs = [nearest]
                 except: all_cs = []
    
            if all_cs:
                 st.write(f"🏭 **{get_text('nearest_cs', lang)}**")
                 
                 # Prepare display data
                 cs_display_list = []
                 for cs in all_cs[:5]:
                      # Special Case: KSR Cold Storage (Hardcoded for accuracy as requested)
                      contact = "N/A"
                      if "KSR" in cs['name'] or "K S R" in cs['name']:
                          contact = "Kari Srinivasa Rao: +91 8008001199"
                      elif cs.get('phone'):
                          contact = cs['phone']
                      else:
                          contact = cs.get('full_address', 'N/A')
                      
                      cs_display_list.append({
                          "Facility Name": cs['name'],
                          "Distance (km)": cs['distance'],
                          "Contact": contact,
                          "Action": f"[📍 Navigate]({cs['map']})"
                      })
                 
                 # Render custom markdown table for clickable links
                 table_header = "| Facility Name | Distance (km) | Contact | Action |\n| :--- | :--- | :--- | :--- |\n"
                 table_rows = ""
                 for cs in cs_display_list:
                      table_rows += f"| {cs['Facility Name']} | {cs['Distance (km)']} | {cs['Contact']} | {cs['Action']} |\n"
                 
                 st.markdown(table_header + table_rows)
                 st.caption("ℹ️ Click '📍 Navigate' to open directions in Google Maps.")
            else:
                 st.warning("No cold storage facilities found within 1000km.")
    
    
            # Profit Roadmap Visualization
            if profit_roadmap:
                st.divider()
                st.header("📈 Profit Roadmap & Forecast")
                
                df_plot = pd.DataFrame(profit_roadmap)
                
                # 2. Forecast Slider
                max_days = int(df_plot['Day'].max())
                selected_days = st.slider(
                    "📅 Forecast Lookahead (Days)", 
                    min_value=0, max_value=max_days, value=rec_days,
                    help="Slide to see how profit changes over time."
                )
                
                # Filter based on slider
                df_filtered = df_plot[df_plot['Day'] <= selected_days].copy()
                
                # 3. Visual Chart (Altair for better control)
                import altair as alt
                
                # Add current profit as a benchmark baseline
                current_profit_val = sell_profit
                
                # Create a baseline dataframe
                df_baseline = pd.DataFrame({'Profit': [current_profit_val], 'Label': ['Sell Now']})
                
                # Baseline rule
                baseline = alt.Chart(df_baseline).mark_rule(
                    color='#e74c3c', 
                    strokeDash=[5, 5], 
                    size=2
                ).encode(
                    y='Profit:Q'
                )
                
                # Baseline text
                baseline_text = alt.Chart(df_baseline).mark_text(
                    align='left', 
                    dx=5, 
                    dy=-10, 
                    color='#e74c3c',
                    fontWeight='bold'
                ).encode(
                    y='Profit:Q',
                    text=alt.value('Current Profit')
                )

                # Main chart
                # Calculate profit increase % for tooltips
                df_filtered['Increase %'] = ((df_filtered['Profit'] - current_profit_val) / abs(current_profit_val) * 100).round(1) if current_profit_val != 0 else 0
                
                line = alt.Chart(df_filtered).mark_line(
                    point=alt.OverlayMarkDef(color='#2ecc71', size=60), 
                    color='#2ecc71',
                    size=3
                ).encode(
                    x=alt.X('Date:N', sort=None, title='Date'),
                    y=alt.Y('Profit:Q', title='Net Profit (₹)', scale=alt.Scale(zero=False)),
                    tooltip=[
                        alt.Tooltip('Date:N', title='Prediction Date'),
                        alt.Tooltip('Profit:Q', title='Net Profit (₹)', format=','),
                        alt.Tooltip('Increase %:Q', title='Gain vs Now (%)'),
                        alt.Tooltip('StorageCost:Q', title='Total Storage Cost (₹)')
                    ]
                ).properties(
                    title='📈 Profit Potential Over Time',
                    height=350
                )
                
                # Combine
                final_chart = (baseline + baseline_text + line).configure_axis(
                    labelFontSize=12,
                    titleFontSize=14
                ).configure_title(
                    fontSize=18,
                    anchor='middle',
                    color='#2ecc71'
                )
                
                st.altair_chart(final_chart, use_container_width=True)
                
                # 4. Interactive Recommendation Text
                if selected_days == rec_days:
                    st.success(f"🌟 **Recommended Strategy:** Store for **{rec_days} days** until **{rec_date}** for maximum profit of **₹{int(stored_profit)}**.")
                else:
                    target_row = df_filtered[df_filtered['Day'] == selected_days].iloc[0]
                    st.info(f"💡 Selling on **{target_row['Date']}** yields a net profit of **₹{int(target_row['Profit'])}** (including ₹{int(target_row['StorageCost'])} storage cost).")

                # Detailed data remains in expander
                with st.expander("📊 View Detailed Analysis Table"):
                    df_display = df_plot[["Date", "Profit", "StorageCost"]].copy()
                    df_display.columns = ["Date", "Net Profit (₹)", "Storage Cost (₹)"]
                    st.dataframe(df_display, use_container_width=True)
    
        # Final Summary for Text-to-Speech
        speech_summary = f"Best Strategy: {'Sell Now' if not should_store else f'Store for {rec_days} days'}. " \
                         f"Estimated profit: ₹{int(stored_profit if should_store else sell_profit)}."
        
        speak_full(speech_summary, st.session_state.lang)
