import streamlit as st
from PIL import Image
import exifread
from streamlit_folium import st_folium
import folium
from datetime import datetime
from typing import Optional, Tuple, Dict
from geopy.geocoders import Nominatim
import requests


class PhotoMetadataExtractor:
    """Handles extraction of metadata from photo files."""
    
    def __init__(self):
        self.geolocator = Nominatim(user_agent="photo-location-app")
    
    def get_gps_coordinates(self, tags: dict) -> Optional[Tuple[float, float]]:
        """Extract GPS coordinates from EXIF tags."""
        gps_latitude = tags.get('GPS GPSLatitude')
        gps_latitude_ref = tags.get('GPS GPSLatitudeRef')
        gps_longitude = tags.get('GPS GPSLongitude')
        gps_longitude_ref = tags.get('GPS GPSLongitudeRef')
        
        if not all([gps_latitude, gps_latitude_ref, gps_longitude, gps_longitude_ref]):
            return None
            
        def to_degrees(value):
            """Convert GPS coordinates to decimal degrees."""
            d, m, s = [float(x.num) / float(x.den) for x in value.values]
            return d + (m / 60.0) + (s / 3600.0)
        
        lat = to_degrees(gps_latitude)
        if gps_latitude_ref.values[0] != 'N':
            lat = -lat
            
        lon = to_degrees(gps_longitude)
        if gps_longitude_ref.values[0] != 'E':
            lon = -lon
            
        return lat, lon

    @staticmethod
    def get_date_taken(tags: dict) -> Optional[str]:
        """Extract and format the date the photo was taken."""
        date_taken = tags.get('EXIF DateTimeOriginal') or tags.get('Image DateTime')
        if not date_taken:
            return None
            
        try:
            # EXIF date format: YYYY:MM:DD HH:MM:SS
            dt = datetime.strptime(str(date_taken), "%Y:%m:%d %H:%M:%S")
            return dt.strftime("%d %B %Y")
        except Exception:
            return str(date_taken)

    def get_address(self, lat: float, lon: float) -> Optional[Dict[str, str]]:
        """Get detailed address information from coordinates using reverse geocoding."""
        try:
            location = self.geolocator.reverse(f"{lat}, {lon}", exactly_one=True)
            if location and location.raw:
                address = location.raw.get('address', {})
                return {
                    'country': address.get('country', ''),
                    'state': address.get('state', '') or address.get('province', ''),
                    'city': address.get('city', '') or address.get('town', '') or address.get('village', ''),
                    'county': address.get('county', ''),
                    'suburb': address.get('suburb', '') or address.get('neighbourhood', ''),
                    'postcode': address.get('postcode', ''),
                    'road': address.get('road', ''),
                    'house_number': address.get('house_number', '')
                }
        except Exception as e:
            st.error(f"Error getting address details: {str(e)}")
        return None

    def get_location_details(self, lat: float, lon: float) -> Optional[Dict[str, str]]:
        """Get location details using direct Nominatim API call."""
        try:
            url = f"https://nominatim.openstreetmap.org/reverse?lat={lat}&lon={lon}&format=json&accept-language=en"
            response = requests.get(url, headers={'User-Agent': 'photo-location-app'})
            
            if response.status_code == 200:
                data = response.json()
                address = data.get("address", {})
                country = address.get("country", "")
                country_code = address.get("country_code", "").upper()
                town = address.get("town", "") or address.get("city", "") or address.get("village", "")

                return {
                    'country': country,
                    'country_code': country_code,
                    'town': town,
                    'display_name': data.get('display_name', ''),
                    'data': data
                }
        except Exception as e:
            st.error(f"Error getting location details: {str(e)}")
        return None


class MapRenderer:
    """Handles map rendering functionality."""
    
    @staticmethod
    def create_location_map(lat: float, lon: float) -> folium.Map:
        """Create a folium map with a marker at the specified coordinates."""
        map_obj = folium.Map(location=[lat, lon], zoom_start=15)
        folium.Marker([lat, lon], popup="Photo Location").add_to(map_obj)
        return map_obj


class PhotoLocationUI:
    """Handles the Streamlit UI components."""
    
    def __init__(self):
        self.metadata_extractor = PhotoMetadataExtractor()
        self.map_renderer = MapRenderer()
    
    def setup_page(self):
        """Configure the Streamlit page."""
        st.set_page_config(page_title="Photo Location", layout="centered")
        st.title("Photo Location")
        st.write("Upload a photo to extract and visualize its location from metadata.")
    
    def display_metadata(self, date_taken: Optional[str], coordinates: Optional[Tuple[float, float]], address_details: Optional[Dict[str, str]] = None, location_details: Optional[Dict[str, str]] = None):
        """Display photo metadata in a formatted layout."""
        with st.container():
            col1, col2 = st.columns(2)
            
            with col1:
                if date_taken:
                    st.markdown(f"<span style='font-size:1.1em'><b>Date Taken:</b> {date_taken}</span>", 
                              unsafe_allow_html=True)
                else:
                    st.markdown("<span style='font-size:1.1em'><b>Date Taken:</b> <i>Not found</i></span>", 
                              unsafe_allow_html=True)
            
            with col2:
                if coordinates:
                    lat, lon = coordinates
                    st.markdown(f"<span style='font-size:1.1em'><b>Coordinates:</b> {lat:.6f}, {lon:.6f}</span>", 
                              unsafe_allow_html=True)
                else:
                    st.markdown("<span style='font-size:1.1em'><b>Coordinates:</b> <i>Not found</i></span>", 
                              unsafe_allow_html=True)
        
        # Display location details (country and country code)
        if location_details:
            st.subheader("🌍 Location")
            # print(location_details)
            town = location_details.get('town', '')
            country = location_details.get('country', '')
            country_code = location_details.get('country_code', '')
            full_data = location_details.get('data', {})
            if country and country_code:
                st.markdown(f"**Country:** {country} ({country_code}) / **Town:** {town}")
            if location_details.get('display_name'):
                st.markdown(f"**Full Location:** {location_details['display_name']}")
            if full_data:
                with st.expander("Full Location Data"):
                    st.markdown("**Full Location Data:**")
                    st.json(full_data)

        # Display detailed address information
        if address_details:
            st.subheader("📍 Address Details")
            detail_col1, detail_col2 = st.columns(2)
            
            with detail_col1:
                if address_details.get('country'):
                    st.markdown(f"**Country:** {address_details['country']}")
                if address_details.get('state'):
                    st.markdown(f"**State/Province:** {address_details['state']}")
                if address_details.get('city'):
                    st.markdown(f"**City:** {address_details['city']}")
                if address_details.get('county'):
                    st.markdown(f"**County:** {address_details['county']}")
            
            with detail_col2:
                if address_details.get('suburb'):
                    st.markdown(f"**Suburb/Neighborhood:** {address_details['suburb']}")
                if address_details.get('road'):
                    st.markdown(f"**Street:** {address_details['road']}")
                if address_details.get('house_number'):
                    st.markdown(f"**House Number:** {address_details['house_number']}")
                if address_details.get('postcode'):
                    st.markdown(f"**Postal Code:** {address_details['postcode']}")
        elif coordinates and not location_details:
            st.info("📍 Getting location details...")
    
    def display_map(self, coordinates: Optional[Tuple[float, float]]):
        """Display the location map if coordinates are available."""
        if coordinates:
            lat, lon = coordinates
            map_obj = self.map_renderer.create_location_map(lat, lon)
            st_folium(map_obj, width=700, height=500)
    
    def process_uploaded_file(self, uploaded_file):
        """Process the uploaded photo file and extract metadata."""
        image = Image.open(uploaded_file)
        st.image(image, caption="Uploaded Photo", use_container_width=True)
        
        # Reset file pointer and extract EXIF data
        uploaded_file.seek(0)
        tags = exifread.process_file(uploaded_file, details=False)
        
        # Extract metadata
        coordinates = self.metadata_extractor.get_gps_coordinates(tags)
        date_taken = self.metadata_extractor.get_date_taken(tags)
        
        # Get location details and address if coordinates are available
        location_details = None
        address_details = None
        if coordinates:
            lat, lon = coordinates
            location_details = self.metadata_extractor.get_location_details(lat, lon)
            address_details = self.metadata_extractor.get_address(lat, lon)
        
        # Display metadata and map
        self.display_metadata(date_taken, coordinates, address_details, location_details)
        self.display_map(coordinates)


def main():
    """Main application function."""
    app = PhotoLocationUI()
    app.setup_page()
    
    uploaded_file = st.file_uploader("Choose a photo", type=["jpg", "jpeg", "png"])
    
    if uploaded_file:
        app.process_uploaded_file(uploaded_file)


if __name__ == "__main__":
    main()
