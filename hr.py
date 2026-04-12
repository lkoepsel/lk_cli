import hashlib
from PIL import Image

def hash_pixel_data(path: str) -> str:
    with Image.open(path) as img:
        rgb = img.convert("RGB")   # normalize color space
        return hashlib.sha256(rgb.tobytes()).hexdigest()

print(hash_pixel_data("card1/photo.jpg"))
print(hash_pixel_data("card2/photo.jpg"))
