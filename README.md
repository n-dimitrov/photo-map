# Photo Location Extractor

A modern Streamlit application that extracts GPS location and date information from uploaded photos and visualizes them on an interactive map.

## Features

- 📷 **Photo Upload**: Support for JPG, JPEG, and PNG formats
- 📍 **GPS Extraction**: Automatically extracts GPS coordinates from EXIF metadata
- 📅 **Date Extraction**: Retrieves and formats the date when the photo was taken
- 🗺️ **Interactive Map**: Visualizes photo location using Folium maps
- 🎨 **Clean UI**: Modern, responsive interface with organized layout
- 🔧 **Robust Code**: Object-oriented architecture with proper error handling

## Technical Architecture

The application is built with a clean, modular architecture:

- **PhotoMetadataExtractor**: Handles EXIF data extraction and processing
- **MapRenderer**: Manages interactive map creation and marker placement
- **PhotoLocationUI**: Controls the Streamlit user interface and workflow

## Requirements

- Python 3.8+
- Streamlit
- Pillow (PIL)
- ExifRead
- Streamlit-folium
- Folium

## Installation & Setup

1. **Clone or download this project**
2. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```
3. **Run the application:**
   ```bash
   streamlit run app.py
   ```
4. **Open your browser** to the displayed URL (typically http://localhost:8501)

## How to Use

1. Click "Choose a photo" and upload an image file
2. The app will display:
   - The uploaded photo
   - Date taken (if available in metadata)
   - GPS coordinates (if available in metadata)
   - Interactive map with location marker (if GPS data exists)

## Supported Metadata

- **GPS Information**: Latitude, Longitude, and coordinate references
- **Date Information**: EXIF DateTimeOriginal or Image DateTime
- **Image Formats**: JPEG, JPG, PNG

## Notes

- Photos without GPS metadata will show "Location: Not found"
- Photos without date metadata will show "Date Taken: Not found"
- The app only extracts existing metadata and cannot determine location from image content
- GPS coordinates are displayed with 6 decimal places for precision

## Development

The codebase uses:
- Type hints for better code documentation
- Class-based architecture for maintainability
- Proper error handling and validation
- Modular design for easy testing and extension
