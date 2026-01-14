import sys
import os
from PIL import Image

def convert():
    # Look for icon in the local Taskwire source directory or root
    source = "app_icon.png"
    if not os.path.exists(source):
        source = os.path.join("Taskwire", "app_icon.png")
    
    dest = "app_icon.ico"
    
    if not os.path.exists(source):
        print(f"Error: Source icon not found at {source} or ./app_icon.png")
        sys.exit(1)
        
    print(f"Converting {source} to {dest}...")
    try:
        img = Image.open(source)
        # Create a high-quality ICO including multiple sizes
        img.save(dest, format='ICO', sizes=[(256, 256), (128, 128), (64, 64), (48, 48), (32, 32), (16, 16)])
        print("Conversion successful.")
    except Exception as e:
        print(f"Error converting icon: {e}")
        sys.exit(1)

if __name__ == "__main__":
    convert()
