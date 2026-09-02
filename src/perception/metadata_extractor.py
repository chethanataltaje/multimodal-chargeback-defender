import exifread
import logging

# Configure basic logging for pipeline visibility
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("MetadataExtractor")

class ImageForensics:
    def __init__(self):
        pass

    def extract_metadata(self, image_path: str) -> dict:
        """
        Reads EXIF data from an image file.
        Returns structured GPS latitude/longitude and capture timestamp when available.
        """
        try:
            with open(image_path, 'rb') as f:
                tags = exifread.process_file(f, details=False)
        except Exception as e:
            logger.error(f"Failed to read image {image_path}: {e}")
            return self._fallback_stripped_response()

        if not tags:
            logger.warning(f"EXIF metadata unavailable for {image_path}.")
            return self._fallback_stripped_response()

        # Camera make/model
        make = str(tags.get('Image Make', '')).strip()
        model = str(tags.get('Image Model', '')).strip()
        camera = f"{make} {model}".strip() if (make or model) else "Camera Model Present in File"

        # GPS extraction – convert to decimal degrees if present
        def _to_decimal(coord):
            # coord is a list of Rational objects (deg, min, sec)
            d, m, s = coord
            deg = float(d.num) / float(d.den)
            minute = float(m.num) / float(m.den)
            sec = float(s.num) / float(s.den)
            return deg + (minute / 60.0) + (sec / 3600.0)

        gps_lat = None
        gps_lon = None
        if all(k in tags for k in ['GPS GPSLatitude', 'GPS GPSLatitudeRef', 'GPS GPSLongitude', 'GPS GPSLongitudeRef']):
            try:
                lat = _to_decimal(tags['GPS GPSLatitude'].values)
                lon = _to_decimal(tags['GPS GPSLongitude'].values)
                if str(tags['GPS GPSLatitudeRef']).upper() == 'S':
                    lat = -lat
                if str(tags['GPS GPSLongitudeRef']).upper() == 'W':
                    lon = -lon
                gps_lat = lat
                gps_lon = lon
            except Exception as ex:
                logger.warning(f"Failed to parse GPS EXIF for {image_path}: {ex}")

        # Timestamp extraction – prefer original capture time
        timestamp = None
        if 'EXIF DateTimeOriginal' in tags:
            timestamp = str(tags['EXIF DateTimeOriginal'])
        elif 'Image DateTime' in tags:
            timestamp = str(tags['Image DateTime'])

        has_telemetry = bool(camera or gps_lat is not None or gps_lon is not None or timestamp)
        if not has_telemetry:
            return self._fallback_stripped_response()

        gps_available = bool(gps_lat is not None and gps_lon is not None)
        timestamp_available = bool(timestamp and str(timestamp).strip())
        logger.info(f"EXIF metadata found for {image_path}. GPS={gps_available}, Timestamp={timestamp_available}")
        return {
            "metadata_available": True,
            "gps_available": gps_available,
            "timestamp_available": timestamp_available,
            "metadata_match": True,  # Maintained strictly for legacy model feature input mapping
            "camera_device": camera,
            "gps_coordinates": {
                "latitude": gps_lat,
                "longitude": gps_lon
            } if gps_available else None,
            "capture_timestamp": timestamp,
            "flag": "EXIF_AVAILABLE",
            "exif_note": "EXIF metadata was present in the submitted file. Metadata presence alone does not establish image originality or authenticity."
        }

    def _fallback_stripped_response(self) -> dict:
        return {
            "metadata_available": False,
            "gps_available": False,
            "timestamp_available": False,
            "metadata_match": False,
            "camera_device": None,
            "gps_coordinates": None,
            "capture_timestamp": None,
            "flag": "EXIF_UNAVAILABLE",
            "exif_note": "No camera metadata was present in the submitted file. Capture time, device information, and GPS location could not be independently verified."
        }

# Instantiate for easy importing
forensics = ImageForensics()

if __name__ == "__main__":
    from PIL import Image
    import os
    
    test_img_path = "test_dummy.jpg"
    img = Image.new('RGB', (100, 100), color='red')
    img.save(test_img_path)
    
    print("\n--- Testing Metadata Extractor ---")
    result = forensics.extract_metadata(test_img_path)
    print(f"Result: {result}\n")
    
    if os.path.exists(test_img_path):
        os.remove(test_img_path)