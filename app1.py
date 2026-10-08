import xml.etree.ElementTree as ET
import streamlit as st
import pydeck as pdk
import openrouteservice
import pandas as pd
from streamlit_js_eval import get_geolocation

# ---------------------------------------------------------
# Page Configuration & Custom CSS
# ---------------------------------------------------------
# ---------------------------------------------------------
# Custom CSS for Full Dark Theme (Background & Font Colors)
# ---------------------------------------------------------
st.markdown("""
<style>
    /* 1. Main App Background & Global Text Color */
    .stApp {
        background-color: #0F172A !important; /* Deep Slate Background */
        color: #F8FAFC !important;           /* Off-White Core Text */
    }

    /* 2. Sidebar Background & Typography */
    [data-testid="stSidebar"] {
        background-color: #1E293B !important;
        border-right: 1px solid #334155;
    }
    [data-testid="stSidebar"] * {
        color: #E2E8F0 !important;           /* Light text in sidebar */
    }

    /* 3. Metric Cards */
    .metric-card {
        background: #1E293B;
        padding: 18px 24px;
        border-radius: 12px;
        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.3);
        border: 1px solid #334155;
        text-align: center;
    }
    .metric-value {
        font-size: 28px;
        font-weight: 700;
        color: #38BDF8 !important;          /* Accent Cyan */
        margin-top: 4px;
    }
    .metric-label {
        font-size: 13px;
        font-weight: 600;
        color: #94A3B8 !important;          /* Soft Slate Text */
        text-transform: uppercase;
        letter-spacing: 0.5px;
    }

    /* 4. Headings & Titles */
    .main-title {
        font-size: 32px;
        font-weight: 800;
        color: #F8FAFC !important;
        margin-bottom: 2px;
    }
    .sub-title {
        font-size: 15px;
        color: #94A3B8 !important;
        margin-bottom: 24px;
    }
    h1, h2, h3, h4, h5, h6, label {
        color: #F8FAFC !important;
    }

    /* 5. Inputs, Selectboxes, and Sliders */
    div[data-baseweb="select"] > div, 
    input {
        background-color: #0F172A !important;
        color: #F8FAFC !important;
        border-color: #334155 !important;
    }
    .stSlider > div {
        color: #F8FAFC !important;
    }

    /* 6. Buttons */
    .stButton > button {
        border-radius: 8px;
        font-weight: 600;
        background-color: #38BDF8 !important;
        color: #0F172A !important;
        border: none !important;
        transition: all 0.2s ease;
    }
    .stButton > button:hover {
        background-color: #7DD3FC !important;
        color: #0F172A !important;
    }

    /* 7. Tabs Styling */
    .stTabs [data-baseweb="tab-list"] {
        background-color: #0F172A;
        border-bottom: 1px solid #334155;
    }
    .stTabs [data-baseweb="tab"] {
        color: #94A3B8 !important;
    }
    .stTabs [aria-selected="true"] {
        color: #38BDF8 !important;
        border-bottom-color: #38BDF8 !important;
    }

    /* 8. Data Tables (Turn-by-Turn Steps) */
    [data-testid="stDataFrame"] {
        background-color: #1E293B !important;
    }
</style>
""", unsafe_allow_html=True)

# ---------------------------------------------------------
# Helper Functions
# ---------------------------------------------------------
def geojson_to_gpx(geojson_data):
    """Converts GeoJSON route features into valid GPX XML."""
    gpx = ET.Element('gpx', version='1.1', creator='CanopyStride', xmlns='http://www.topografix.com/GPX/1/1')
    trk = ET.SubElement(gpx, 'trk')
    trkseg = ET.SubElement(trk, 'trkseg')

    if geojson_data.get("type") == "FeatureCollection":
        coords = geojson_data["features"][0]["geometry"]["coordinates"]
    elif geojson_data.get("type") == "Feature":
        coords = geojson_data["geometry"]["coordinates"]
    else:
        coords = geojson_data.get("coordinates", [])

    for lon, lat in coords:
        ET.SubElement(trkseg, 'trkpt', lat=str(lat), lon=str(lon))

    return ET.tostring(gpx, encoding='utf-8', xml_declaration=True).decode('utf-8')

# ---------------------------------------------------------
# Session State & Geolocation Initialization
# ---------------------------------------------------------
loc = get_geolocation()

if loc and "coords" in loc:
    user_lat = loc["coords"]["latitude"]
    user_lon = loc["coords"]["longitude"]
    if "location_set" not in st.session_state:
        st.session_state["start_lat"] = user_lat
        st.session_state["start_lon"] = user_lon
        st.session_state["location_set"] = True
else:
    if "start_lon" not in st.session_state:
        st.session_state["start_lon"] = 76.3860
    if "start_lat" not in st.session_state:
        st.session_state["start_lat"] = 30.3398

# ---------------------------------------------------------
# Sidebar Controls
# ---------------------------------------------------------
with st.sidebar:
    st.image("https://img.icons8.com/fluency/96/running.png", width=64)
    st.title("CanopyStride")
    st.caption("Custom Circular Route Planner")
    st.markdown("---")

    # API Configuration Section
    api_key = st.secrets.get("ORS_API_KEY", None)
    if not api_key:
        api_key = st.text_input("OpenRouteService API Key", type="password", help="Enter your free ORS API key.")
        if not api_key:
            st.warning("⚠️ API Key required to calculate real routes.")
            st.stop()

    client = openrouteservice.Client(key=api_key, base_url="https://api.heigit.org/openrouteservice")

    # Run Settings
    st.subheader("⚙️ Route Parameters")
    
    if st.button("🎯 Detect My Location", use_container_width=True):
        if loc and "coords" in loc:
            st.session_state["start_lat"] = loc["coords"]["latitude"]
            st.session_state["start_lon"] = loc["coords"]["longitude"]
            st.success("Location synced successfully!")
            st.rerun()
        else:
            st.error("Browser location permission needed.")

    profile = st.selectbox(
        "Activity Profile",
        options=["foot-walking", "foot-hiking"],
        format_func=lambda x: "🏃‍♂️ Road Running / Walking" if x == "foot-walking" else "🥾 Trail / Nature Hiking"
    )

    target_distance = st.slider(
        "Target Distance (km)", 
        min_value=1.0, 
        max_value=25.0, 
        value=5.0, 
        step=0.5,
        help="ORS will automatically shape a circular loop near this distance."
    )

    # 🗺️ Map Theme Selector
    st.markdown("---")
    st.subheader("🎨 Map Style")
    map_theme = st.radio(
        "Select Theme",
        options=["Light", "Dark", "Satellite"],
        horizontal=True,
        index=0
    )

    with st.expander("📍 Custom Coordinates"):
        start_lon = st.number_input("Start Longitude", value=float(st.session_state["start_lon"]), format="%.4f")
        start_lat = st.number_input("Start Latitude", value=float(st.session_state["start_lat"]), format="%.4f")
        st.session_state["start_lon"] = start_lon
        st.session_state["start_lat"] = start_lat

    st.markdown("---")
    generate_btn = st.button("🚀 Generate Loop Route", type="primary", use_container_width=True)

# ---------------------------------------------------------
# Main Interface Area
# ---------------------------------------------------------
st.markdown('<div class="main-title">🏃 Route Dashboard</div>', unsafe_allow_html=True)
st.markdown('<div class="sub-title">Generate custom closed-loop walking and running paths from your exact location.</div>', unsafe_allow_html=True)

@st.cache_data(ttl=3600)
def fetch_round_trip(coords, profile_name, dist_km, token):
    try:
        dist_meters = int(dist_km * 1000)
        return client.directions(
            coordinates=coords,
            profile=profile_name,
            format="geojson",
            options={"round_trip": {"length": dist_meters, "points": 5}},
            radiuses=[-1],
            validate=False
        )
    except Exception as e:
        st.error(f"Routing Error: {e}")
        return None

waypoints = [[st.session_state["start_lon"], st.session_state["start_lat"]]]

if generate_btn:
    with st.spinner("Calculating optimal round-trip loop..."):
        route_geojson = fetch_round_trip(waypoints, profile, target_distance, api_key)

    if route_geojson:
        summary = route_geojson["features"][0]["properties"]["summary"]
        actual_distance_km = round(summary["distance"] / 1000, 2)
        duration_min = round(summary["duration"] / 60, 1)
        est_calories = int(actual_distance_km * 65)

        # Top Metric Cards Grid
        m1, m2, m3, m4 = st.columns(4)
        m1.markdown(f'''<div class="metric-card"><div class="metric-label">Target Distance</div><div class="metric-value">{target_distance} km</div></div>''', unsafe_allow_html=True)
        m2.markdown(f'''<div class="metric-card"><div class="metric-label">Actual Distance</div><div class="metric-value">{actual_distance_km} km</div></div>''', unsafe_allow_html=True)
        m3.markdown(f'''<div class="metric-card"><div class="metric-label">Est. Duration</div><div class="metric-value">{duration_min} min</div></div>''', unsafe_allow_html=True)
        m4.markdown(f'''<div class="metric-card"><div class="metric-label">Est. Energy</div><div class="metric-value">~{est_calories} kcal</div></div>''', unsafe_allow_html=True)

        st.markdown("<br>", unsafe_allow_html=True)

        tab_map, tab_steps, tab_export = st.tabs(["🗺️ Interactive Map", "📋 Turn-by-Turn Steps", "📥 Export & Download"])

        line_coords = route_geojson["features"][0]["geometry"]["coordinates"]

        with tab_map:
            # Color adjustments for better visibility across different map themes
            path_color = [255, 87, 87] if map_theme == "Dark" else ([255, 230, 0] if map_theme == "Satellite" else [239, 68, 68])

            # Path Layer
            path_layer = pdk.Layer(
                "PathLayer",
                data=[{"path": line_coords}],
                get_path="path",
                get_color=path_color,
                width_min_pixels=6,
                pickable=True
            )

            # Start/Origin Marker Layer
            origin_data = [{"coordinates": [st.session_state["start_lon"], st.session_state["start_lat"]], "name": "Start/End Point"}]
            icon_layer = pdk.Layer(
                "ScatterplotLayer",
                data=origin_data,
                get_position="coordinates",
                get_color=[16, 185, 129],
                get_radius=30,
                radius_min_pixels=9,
                pickable=True
            )

            # Configure Map Layer & Base Style
            extra_layers = [path_layer, icon_layer]
            pydeck_style = None

            if map_theme == "Light":
                pydeck_style = "light"
            elif map_theme == "Dark":
                pydeck_style = "dark"
            elif map_theme == "Satellite":
                # Use open-source ESRI Satellite Tile Layer (No Mapbox Token Required)
                satellite_tile_layer = pdk.Layer(
                    "TileLayer",
                    data="https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
                    min_zoom=0,
                    max_zoom=19,
                    tile_size=256,
                )
                extra_layers.insert(0, satellite_tile_layer)

            view_state = pdk.ViewState(
                latitude=st.session_state["start_lat"],
                longitude=st.session_state["start_lon"],
                zoom=14,
                pitch=0
            )

            st.pydeck_chart(
                pdk.Deck(
                    layers=extra_layers,
                    initial_view_state=view_state,
                    map_style=pydeck_style,
                    tooltip={"text": "{name}"}
                )
            )

        with tab_steps:
            st.subheader("Step-by-Step Directions")
            segments = route_geojson["features"][0]["properties"].get("segments", [])
            
            if segments:
                steps_data = []
                for idx, step in enumerate(segments[0].get("steps", []), 1):
                    steps_data.append({
                        "Step": idx,
                        "Instruction": step.get("instruction", "Continue forward"),
                        "Distance": f"{round(step.get('distance', 0), 1)} m",
                        "Duration": f"{round(step.get('duration', 0), 1)} s"
                    })
                st.dataframe(pd.DataFrame(steps_data), use_container_width=True, hide_index=True)
            else:
                st.info("Detailed instructions unavailable for this route.")

        with tab_export:
            st.subheader("Download Route File")
            st.write("Export your calculated loop directly into standard **GPX format** for use with Garmin, Strava, Apple Watch, or handheld GPS devices.")
            
            gpx_data = geojson_to_gpx(route_geojson)
            
            st.download_button(
                label="💾 Download .GPX Route File",
                data=gpx_data,
                file_name=f"canopy_stride_{actual_distance_km}km.gpx",
                mime="application/gpx+xml",
                type="primary"
            )
else:
    st.info("👈 Set your target distance in the sidebar and click **Generate Loop Route** to build your path.")