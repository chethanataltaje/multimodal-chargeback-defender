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
        Explicitly handles EXIF-stripped images (e.g., WhatsApp, screenshots) 
        which are highly correlated with fraudulent claims.
        """
        try:
            with open(image_path, 'rb') as f:
                tags = exifread.process_file(f, details=False)
        except Exception as e:
            logger.error(f"Failed to read image {image_path}: {e}")
            return self._fallback_stripped_response()

        # If no tags are found, or critical GPS/Date tags are missing, 
        # we treat it as a stripped image.
        if not tags or 'GPS GPSLatitude' not in tags:
            logger.warning(f"EXIF stripped or unavailable for {image_path}.")
            return self._fallback_stripped_response()
            
        # Simplistic extraction for demo purposes. In a real production system,
        # these would be cross-referenced mathematically against the delivery manifest.
        logger.info("EXIF data intact. Extracting forensics.")
        return {
            "metadata_available": True,
            "metadata_match": True,  # Simulated match for the demo
            "gps_coordinates": str(tags.get('GPS GPSLatitude')),
            "capture_timestamp": str(tags.get('Image DateTime')),
            "flag": "EXIF_INTACT"
        }

    def _fallback_stripped_response(self) -> dict:
        """
        Standardized response for images lacking EXIF data.
        This explicitly flags the missing data as a risk signal for the CatBoost model.
        """
        return {
            "metadata_available": False,
            "metadata_match": False,
            "gps_coordinates": None,
            "capture_timestamp": None,
            "flag": "EXIF_STRIPPED_OR_UNAVAILABLE"
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