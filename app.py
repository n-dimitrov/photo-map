# app.py
# Streamlit Photo Location — robust EXIF + reverse geocoding (Nominatim) with caching and policy-compliant UA

import streamlit as st
from PIL import Image
import exifread
from streamlit_folium import st_folium
import folium
from datetime import datetime
from typing import Optional, Tuple, Dict
import requests
import time
from functools import lru_cache
from streamlit.components.v1 import html

# ──────────────────────────────────────────────────────────────────────────────
# Page config must be first Streamlit call
st.set_page_config(page_title="Photo Location", layout="centered")

# Nominatim policy-compliant User-Agent (ADD YOUR CONTACT)
POLICY_UA = "photo-location-app/1.0 (contact: your.email@example.com)"

# ──────────────────────────────────────────────────────────────────────────────
# Utilities for EXIF parsing

def _ratio_to_float(r):
    """Accept exifread.utils.Ratio or (num, den) tuple."""
    try:
        return float(r.num) / float(r.den)
    except AttributeError:
        num, den = r
        return float(num) / float(den)

def _dms_to_degrees(values):
    """Convert DMS iterable (2 or 3 parts) to decimal degrees."""
    parts = list(values)
    if len(parts) == 2:
        d, m = (_ratio_to_float(parts[0]), _ratio_to_float(parts[1]))
        s = 0.0
    else:
        d, m, s = (
            _ratio_to_float(parts[0]),
            _ratio_to_float(parts[1]),
            _ratio_to_float(parts[2]),
        )
    return d + m/60.0 + s/3600.0

# ──────────────────────────────────────────────────────────────────────────────
# Reverse geocoding with caching and polite backoff

@lru_cache(maxsize=1024)
def _reverse_cached(lat_rounded: float, lon_rounded: float) -> Optional[dict]:
    """Low-level reverse geocode with retry/backoff and UA; cache by rounded coords."""
    url = "https://nominatim.openstreetmap.org/reverse"
    params = {
        "lat": lat_rounded,
        "lon": lon_rounded,
        "format": "json",
        "accept-language": "en",
    }
    for attempt in range(3):
        try:
            r = requests.get(url, params=params, headers={"User-Agent": POLICY_UA}, timeout=10)
            if r.status_code == 200:
                return r.json()
            if r.status_code == 429:
                time.sleep(1.5 * (attempt + 1))
                continue
            # Non-OK
            return None
        except requests.RequestException:
            time.sleep(0.5 * (attempt + 1))
    return None

def reverse_geocode(lat: float, lon: float) -> Optional[Dict[str, str]]:
    """High-level reverse geocode to normalized dict."""
    # round to ~11m precision to boost cache hits yet keep city-level accuracy
    lat_r = round(lat, 4)
    lon_r = round(lon, 4)
    data = _reverse_cached(lat_r, lon_r)
    if not data:
        return None
    address = data.get("address", {}) or {}
    return {
        "country": address.get("country", ""),
        "country_code": (address.get("country_code", "") or "").upper(),
        "town": address.get("town") or address.get("city") or address.get("village") or "",
        "county": address.get("county", ""),
        "state": address.get("state") or address.get("province") or "",
        "suburb": address.get("suburb") or address.get("neighbourhood") or "",
        "postcode": address.get("postcode", ""),
        "road": address.get("road", ""),
        "house_number": address.get("house_number", ""),
        "display_name": data.get("display_name", ""),
        "raw": data,
    }

@st.cache_data(ttl=86400, show_spinner=False)
def reverse_geocode_cached(lat: float, lon: float) -> Optional[Dict[str, str]]:
    """Streamlit-cached wrapper (per-day) to avoid repeated API calls within the app."""
    return reverse_geocode(lat, lon)

# ──────────────────────────────────────────────────────────────────────────────
# Metadata extractor

class PhotoMetadataExtractor:
    """Handles extraction of metadata from photo files."""

    def get_gps_coordinates(self, tags: dict) -> Optional[Tuple[float, float]]:
        """Extract GPS coordinates from EXIF tags (robust)."""
        lat_tag = tags.get("GPS GPSLatitude")
        lat_ref_tag = tags.get("GPS GPSLatitudeRef")
        lon_tag = tags.get("GPS GPSLongitude")
        lon_ref_tag = tags.get("GPS GPSLongitudeRef")

        if not all([lat_tag, lat_ref_tag, lon_tag, lon_ref_tag]):
            return None

        try:
            lat = _dms_to_degrees(lat_tag.values)
            lon = _dms_to_degrees(lon_tag.values)
            lat_ref = str(lat_ref_tag.values[0]).upper()
            lon_ref = str(lon_ref_tag.values[0]).upper()
            if lat_ref == "S":
                lat = -lat
            if lon_ref == "W":
                lon = -lon
            if not (-90.0 <= lat <= 90.0 and -180.0 <= lon <= 180.0):
                return None
            return (lat, lon)
        except Exception:
            return None

    @staticmethod
    def get_date_taken(tags: dict) -> Optional[str]:
        """Extract and format the date the photo was taken."""
        keys = ["EXIF DateTimeOriginal", "EXIF DateTimeDigitized", "Image DateTime"]
        for k in keys:
            v = tags.get(k)
            if not v:
                continue
            s = str(v)
            for fmt in ("%Y:%m:%d %H:%M:%S", "%Y:%m:%d %H:%M:%S%z"):
                try:
                    dt = datetime.strptime(s, fmt)
                    return dt.strftime("%d %B %Y")
                except Exception:
                    pass
            return s
        return None

# ──────────────────────────────────────────────────────────────────────────────
# Map rendering

class MapRenderer:
    """Handles map rendering functionality."""

    @staticmethod
    def create_location_map(lat: float, lon: float) -> folium.Map:
        """Create a folium map with a marker at the specified coordinates."""
        map_obj = folium.Map(location=[lat, lon], zoom_start=15)
        folium.Marker([lat, lon], popup=str("Photo Location")).add_to(map_obj)
        return map_obj

# ──────────────────────────────────────────────────────────────────────────────
# UI

class PhotoLocationUI:
    """Handles the Streamlit UI components."""

    def __init__(self):
        self.metadata_extractor = PhotoMetadataExtractor()
        self.map_renderer = MapRenderer()

    def header(self):
        st.title("Photo Location")
        st.write("Upload a photo to extract and visualize its location from metadata.")

    def display_metadata(
        self,
        date_taken: Optional[str],
        coordinates: Optional[Tuple[float, float]],
        address: Optional[Dict[str, str]] = None,
    ):
        """Display photo metadata in a formatted layout."""
        with st.container():
            col1, col2 = st.columns(2)

            with col1:
                if date_taken:
                    st.markdown(
                        "<span style='font-size:1.1em'><b>Date Taken:</b> "
                        f"{date_taken}</span>",
                        unsafe_allow_html=True,
                    )
                else:
                    st.markdown(
                        "<span style='font-size:1.1em'><b>Date Taken:</b> "
                        "<i>Not found</i></span>",
                        unsafe_allow_html=True,
                    )

            with col2:
                if coordinates:
                    lat, lon = coordinates
                    st.markdown(
                        "<span style='font-size:1.1em'><b>Coordinates:</b> "
                        f"{lat:.6f}, {lon:.6f}</span>",
                        unsafe_allow_html=True,
                    )
                else:
                    st.markdown(
                        "<span style='font-size:1.1em'><b>Coordinates:</b> "
                        "<i>Not found</i></span>",
                        unsafe_allow_html=True,
                    )

        # Location (country/town/full)
        if address:
            st.subheader("🌍 Location")
            town = address.get("town", "")
            country = address.get("country", "")
            country_code = address.get("country_code", "")
            if country or town:
                st.markdown(
                    f"**Country:** {country} ({country_code})"
                    + (f" / **Town:** {town}" if town else "")
                )
            if address.get("display_name"):
                st.markdown(f"**Full Location:** {address['display_name']}")
            raw = address.get("raw")
            if raw:
                with st.expander("Full Location Data"):
                    st.json(raw)

            # Address details
            st.subheader("📍 Address Details")
            detail_col1, detail_col2 = st.columns(2)
            with detail_col1:
                if address.get("state"):
                    st.markdown(f"**State/Province:** {address['state']}")
                if address.get("county"):
                    st.markdown(f"**County:** {address['county']}")
                if address.get("suburb"):
                    st.markdown(f"**Suburb/Neighborhood:** {address['suburb']}")

            with detail_col2:
                if address.get("road"):
                    st.markdown(f"**Street:** {address['road']}")
                if address.get("house_number"):
                    st.markdown(f"**House Number:** {address['house_number']}")
                if address.get("postcode"):
                    st.markdown(f"**Postal Code:** {address['postcode']}")

        elif coordinates:
            st.info("📍 Getting location details…")

    def display_map(self, coordinates):
        if not coordinates:
            return
        lat, lon = coordinates
        map_obj = self.map_renderer.create_location_map(lat, lon)
        html(map_obj._repr_html_(), height=500)

    def process_uploaded_file(self, uploaded_file):
        """Process the uploaded photo file and extract metadata."""
        # Show image (limit size)
        try:
            image = Image.open(uploaded_file)
            st.image(image, caption="Uploaded Photo", use_column_width=True)
        except Exception:
            st.error("Could not open image.")
            return

        # Reset file pointer and parse EXIF
        uploaded_file.seek(0)
        try:
            tags = exifread.process_file(uploaded_file, details=False)
        except Exception:
            tags = {}

        if not tags:
            st.info("No EXIF metadata found (or metadata stripped).")

        # Extract metadata
        coordinates = self.metadata_extractor.get_gps_coordinates(tags)
        date_taken = self.metadata_extractor.get_date_taken(tags)

        # Reverse geocode if coords present
        address = None
        if coordinates:
            lat, lon = coordinates
            address = reverse_geocode_cached(lat, lon)
        else:
            if tags:
                st.info("Photo has EXIF but no GPS location.")

        # Display metadata and map
        
        self.display_metadata(date_taken, coordinates, address)
        self.display_map(coordinates)

# ──────────────────────────────────────────────────────────────────────────────
# Main

def main():
    ui = PhotoLocationUI()
    ui.header()

    uploaded_file = st.file_uploader("Choose a photo", type=["jpg", "jpeg", "png"])
    if uploaded_file:
        ui.process_uploaded_file(uploaded_file)

if __name__ == "__main__":
    main()