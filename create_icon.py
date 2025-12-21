import tkinter as tk
from tkinter import Canvas
from PIL import Image, ImageDraw, ImageFont, ImageFilter
import math

def create_app_icon(filename="app_icon.png", size=512):
    # Colors from ModernTheme
    BG_COLOR = "#1e1e2e"       # Dark Blue-Black
    ACCENT_PURPLE = "#bd93f9"  # Neon Purple
    ACCENT_CYAN = "#8be9fd"    # Neon Cyan
    ACCENT_PINK = "#ff79c6"    # Neon Pink
    
    # Create a new image with alpha channel
    img = Image.new('RGBA', (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    
    # 1. Background (Rounded Rectangle)
    padding = size * 0.05
    rect_bbox = [padding, padding, size - padding, size - padding]
    radius = size * 0.2
    
    # Draw dark background
    draw.rounded_rectangle(rect_bbox, radius=radius, fill=BG_COLOR)
    
    # 2. Neon Border (Simulated with multiple strokes)
    stroke_width = int(size * 0.03)
    # Outer glow (soft)
    # We can't do real blur easily with basic PIL drawing without filters, 
    # so we'll draw a solid crisp border for the "vector" look.
    draw.rounded_rectangle(rect_bbox, radius=radius, outline=ACCENT_PURPLE, width=stroke_width)
    
    # 3. The "Pulse" Graph Symbol
    # Coordinates for a stylized pulse line
    center_y = size / 2
    left_x = size * 0.2
    right_x = size * 0.8
    width = right_x - left_x
    
    points = [
        (left_x, center_y),
        (left_x + width * 0.2, center_y),
        (left_x + width * 0.35, center_y - size * 0.25), # Peak Up
        (left_x + width * 0.5, center_y + size * 0.25),  # Peak Down
        (left_x + width * 0.65, center_y - size * 0.1),  # Small Peak
        (left_x + width * 0.8, center_y),
        (right_x, center_y)
    ]
    
    # Draw the line
    draw.line(points, fill=ACCENT_CYAN, width=int(size * 0.04), joint="curve")
    
    # 4. Add a "Dot" at the end to signify live data
    dot_radius = size * 0.03
    dot_x, dot_y = points[-1]
    draw.ellipse(
        [dot_x - dot_radius, dot_y - dot_radius, dot_x + dot_radius, dot_y + dot_radius],
        fill=ACCENT_PINK
    )
    
    # Save
    img.save(filename)
    print(f"Icon generated: {filename}")

if __name__ == "__main__":
    try:
        create_app_icon()
    except ImportError:
        print("Pillow (PIL) is not installed. Installing it now...")
        import subprocess
        import sys
        subprocess.check_call([sys.executable, "-m", "pip", "install", "Pillow"])
        create_app_icon()
