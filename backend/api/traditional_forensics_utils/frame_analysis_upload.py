import base64
import tempfile

def save_base64_frame(base64_str):
    """
    Saves a base64-encoded image to a temporary file and returns the file path.
    """
    # Remove the header if present: "data:image/jpeg;base64,"
    if "," in base64_str:
        base64_str = base64_str.split(",")[1]

    img_data = base64.b64decode(base64_str)
    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".jpg")
    temp_file.write(img_data)
    temp_file.close()
    return temp_file.name