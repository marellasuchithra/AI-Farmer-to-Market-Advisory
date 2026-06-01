import cv2
import numpy as np

def analyze_image(uploaded_img):
    """
    Analyzes the uploaded image to determine color quality.
    """
    if uploaded_img is None:
        return "No Image"

    # Reset stream pointer to ensure we read from the beginning
    uploaded_img.seek(0)
    
    file_bytes = np.asarray(
        bytearray(uploaded_img.read()),
        dtype=np.uint8
    )

    img = cv2.imdecode(file_bytes, 1)

    if img is None:
        return "Invalid Image"

    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)

    # Calculate mean of the Saturation channel (approx color intensity)
    # Using channel 1 (Saturation) or 0 (Hue) depending on crop color logic.
    # Original code used channel 1.
    score = hsv[:,:,1].mean()

    if score > 60:
        return "Good Color"
    else:
        return "Poor Color"


def detect_dominant_color(uploaded_img):
    """
    Detects the dominant color family of the image using HSV Hue analysis.
    Returns: 'Red', 'Green', 'Yellow', 'Brown', or 'Unknown'
    """
    if uploaded_img is None:
        return None

    # Reset stream
    uploaded_img.seek(0)
    file_bytes = np.asarray(bytearray(uploaded_img.read()), dtype=np.uint8)
    img = cv2.imdecode(file_bytes, 1)

    if img is None:
        return None

    # Convert to HSV
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    
    # Calculate mask counts for different colors
    # Hue ranges (OpenCV Hue is 0-179)
    
    # Red: 0-10 and 170-179
    lower_red1 = np.array([0, 50, 50])
    upper_red1 = np.array([10, 255, 255])
    lower_red2 = np.array([170, 50, 50])
    upper_red2 = np.array([179, 255, 255])
    
    # Green: 35-85
    lower_green = np.array([35, 50, 50])
    upper_green = np.array([85, 255, 255])
    
    # Yellow: 20-35
    lower_yellow = np.array([20, 50, 50])
    upper_yellow = np.array([35, 255, 255])
    
    # Brown (approx Orange/Red but lower value/sat): 10-20
    # Actually, simplistic brown can be covered under "Orange/Yellow" or "Dark Red"
    # For simplified crop logic: Potato/Onion might fall here.
    
    mask_red1 = cv2.inRange(hsv, lower_red1, upper_red1)
    mask_red2 = cv2.inRange(hsv, lower_red2, upper_red2)
    mask_red = mask_red1 + mask_red2
    
    mask_green = cv2.inRange(hsv, lower_green, upper_green)
    mask_yellow = cv2.inRange(hsv, lower_yellow, upper_yellow)
    
    # Count pixels
    red_pixels = cv2.countNonZero(mask_red)
    green_pixels = cv2.countNonZero(mask_green)
    yellow_pixels = cv2.countNonZero(mask_yellow)
    
    total_pixels = img.shape[0] * img.shape[1]
    
    # Threshold (e.g., if >10% of pixels match)
    # Return the max match
    counts = {"Red": red_pixels, "Green": green_pixels, "Yellow": yellow_pixels}
    max_color = max(counts, key=counts.get)
    
    if counts[max_color] > (0.05 * total_pixels): # at least 5% match
        return max_color
        
    return "Unknown"


# Known dominant colors for common crops
CROP_COLOR_MAP = {
    # Red crops
    "tomato": ["Red"],
    "red chilli": ["Red"],
    "chilly": ["Red", "Green"],
    "apple": ["Red", "Green"],
    "pomegranate": ["Red"],
    "beetroot": ["Red"],
    "watermelon": ["Green", "Red"],
    "strawberry": ["Red"],
    "onion": ["Red", "Yellow"],
    
    # Green crops
    "okra": ["Green"],
    "brinjal": ["Green"],
    "cabbage": ["Green"],
    "spinach": ["Green"],
    "coriander": ["Green"],
    "capsicum": ["Green", "Red", "Yellow"],
    "cucumber": ["Green"],
    "bitter gourd": ["Green"],
    "bottle gourd": ["Green"],
    "ridge gourd": ["Green"],
    "beans": ["Green"],
    "peas": ["Green"],
    "drumstick": ["Green"],
    "green chilli": ["Green"],
    "cauliflower": ["Green"],
    "lettuce": ["Green"],
    "guava": ["Green", "Yellow"],
    
    # Yellow crops
    "banana": ["Yellow", "Green"],
    "mango": ["Yellow", "Green", "Red"],
    "lemon": ["Yellow", "Green"],
    "orange": ["Yellow"],
    "sweet orange": ["Yellow"],
    "mousambi": ["Yellow", "Green"],
    "papaya": ["Yellow", "Green"],
    "pineapple": ["Yellow"],
    "turmeric": ["Yellow"],
    "maize": ["Yellow"],
    "corn": ["Yellow"],
    
    # Brown/Yellow (grains, roots)
    "potato": ["Yellow"],
    "ginger": ["Yellow"],
    "carrot": ["Red", "Yellow"],
    "groundnut": ["Yellow"],
    "coconut": ["Green"],
    
    # Grains — usually yellowish/brown
    "rice": ["Yellow"],
    "wheat": ["Yellow"],
    "paddy": ["Yellow", "Green"],
    "jowar": ["Yellow"],
    "bajra": ["Yellow"],
    "ragi": ["Red"],
}

def verify_crop_image(uploaded_img, crop_name):
    """
    Compares the uploaded image's dominant color against expected colors for the crop.
    Returns: {"match": bool, "detected_color": str, "expected_colors": list, "message": str}
    """
    if uploaded_img is None or not crop_name:
        return {"match": True, "detected_color": "N/A", "expected_colors": [], "message": ""}
    
    detected = detect_dominant_color(uploaded_img)
    
    if detected is None or detected == "Unknown":
        return {"match": True, "detected_color": detected or "Unknown", "expected_colors": [], 
                "message": "Could not determine image color."}
    
    # Lookup expected colors
    crop_lower = crop_name.strip().lower()
    expected_colors = None
    
    # Exact match
    if crop_lower in CROP_COLOR_MAP:
        expected_colors = CROP_COLOR_MAP[crop_lower]
    else:
        # Partial match
        for key, colors in CROP_COLOR_MAP.items():
            if key in crop_lower or crop_lower in key:
                expected_colors = colors
                break
    
    if expected_colors is None:
        # Crop not in our map — can't verify
        return {"match": True, "detected_color": detected, "expected_colors": [], 
                "message": f"Crop '{crop_name}' not in verification database."}
    
    is_match = detected in expected_colors
    
    if is_match:
        message = f"✅ Image color ({detected}) matches expected colors for '{crop_name}'."
    else:
        expected_str = ", ".join(expected_colors)
        message = f"⚠️ The image and crop name you've entered are not the same. Image shows '{detected}' color, but '{crop_name}' is usually {expected_str}."
    
    return {
        "match": is_match,
        "detected_color": detected,
        "expected_colors": expected_colors,
        "message": message
    }
