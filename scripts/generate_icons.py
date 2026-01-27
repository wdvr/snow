#!/usr/bin/env python3
"""
Generate app icons for Powder Chaser and Footprint apps.
Creates 1024x1024 PNG icons suitable for App Store.
"""

import math
from PIL import Image, ImageDraw, ImageFont, ImageFilter
import os


def create_powder_chaser_icon(output_path: str, size: int = 1024):
    """Create a snow/mountain themed icon for Powder Chaser."""

    # Create image with gradient background (sky blue to darker blue)
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # Gradient background - winter sky
    for y in range(size):
        ratio = y / size
        r = int(135 + (200 - 135) * (1 - ratio))  # Light blue at top
        g = int(206 + (230 - 206) * (1 - ratio))
        b = int(250 + (255 - 250) * (1 - ratio))
        draw.line([(0, y), (size, y)], fill=(r, g, b, 255))

    # Draw mountains
    mountain_color_back = (180, 200, 220)  # Lighter mountain in back
    mountain_color_front = (220, 235, 245)  # Snowy mountain in front

    # Back mountain (left)
    points_back = [
        (0, size),
        (0, int(size * 0.55)),
        (int(size * 0.3), int(size * 0.25)),
        (int(size * 0.5), int(size * 0.45)),
        (int(size * 0.6), size),
    ]
    draw.polygon(points_back, fill=mountain_color_back)

    # Front mountain (right, main)
    points_front = [
        (int(size * 0.25), size),
        (int(size * 0.5), int(size * 0.15)),  # Peak
        (int(size * 0.75), int(size * 0.4)),
        (size, int(size * 0.5)),
        (size, size),
    ]
    draw.polygon(points_front, fill=mountain_color_front)

    # Snow cap on main mountain
    snow_cap = [
        (int(size * 0.42), int(size * 0.28)),
        (int(size * 0.5), int(size * 0.15)),
        (int(size * 0.58), int(size * 0.28)),
    ]
    draw.polygon(snow_cap, fill=(255, 255, 255))

    # Add snowflakes
    snowflake_positions = [
        (size * 0.15, size * 0.12),
        (size * 0.8, size * 0.08),
        (size * 0.9, size * 0.25),
        (size * 0.12, size * 0.35),
        (size * 0.7, size * 0.18),
        (size * 0.25, size * 0.22),
    ]

    for x, y in snowflake_positions:
        draw_snowflake(draw, int(x), int(y), int(size * 0.04))

    # Add subtle shadow/glow effect
    img = img.filter(ImageFilter.GaussianBlur(radius=1))

    # Round corners for iOS style
    img = add_rounded_corners(img, int(size * 0.22))

    img.save(output_path, "PNG")
    print(f"Created Powder Chaser icon: {output_path}")


def draw_snowflake(draw, cx, cy, size):
    """Draw a simple 6-pointed snowflake."""
    color = (255, 255, 255, 200)

    for angle in range(0, 360, 60):
        rad = math.radians(angle)
        x2 = cx + int(size * math.cos(rad))
        y2 = cy + int(size * math.sin(rad))
        draw.line([(cx, cy), (x2, y2)], fill=color, width=max(2, size // 8))


def create_footprint_icon(output_path: str, size: int = 1024):
    """Create a world map with pins icon for Footprint."""

    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # Background gradient - ocean blue
    for y in range(size):
        ratio = y / size
        r = int(30 + (50 - 30) * ratio)
        g = int(100 + (140 - 100) * ratio)
        b = int(180 + (200 - 180) * ratio)
        draw.line([(0, y), (size, y)], fill=(r, g, b, 255))

    # Draw simplified world map continents
    continent_color = (80, 160, 100)  # Green for land

    # North America (simplified)
    na_points = [
        (size * 0.12, size * 0.25),
        (size * 0.18, size * 0.18),
        (size * 0.28, size * 0.15),
        (size * 0.35, size * 0.22),
        (size * 0.32, size * 0.35),
        (size * 0.28, size * 0.45),
        (size * 0.22, size * 0.52),
        (size * 0.15, size * 0.48),
        (size * 0.10, size * 0.38),
    ]
    draw.polygon([(int(x), int(y)) for x, y in na_points], fill=continent_color)

    # South America (simplified)
    sa_points = [
        (size * 0.22, size * 0.55),
        (size * 0.28, size * 0.52),
        (size * 0.32, size * 0.58),
        (size * 0.30, size * 0.72),
        (size * 0.26, size * 0.82),
        (size * 0.22, size * 0.78),
        (size * 0.20, size * 0.65),
    ]
    draw.polygon([(int(x), int(y)) for x, y in sa_points], fill=continent_color)

    # Europe (simplified)
    eu_points = [
        (size * 0.45, size * 0.20),
        (size * 0.52, size * 0.18),
        (size * 0.58, size * 0.22),
        (size * 0.55, size * 0.32),
        (size * 0.48, size * 0.35),
        (size * 0.42, size * 0.30),
    ]
    draw.polygon([(int(x), int(y)) for x, y in eu_points], fill=continent_color)

    # Africa (simplified)
    af_points = [
        (size * 0.48, size * 0.38),
        (size * 0.58, size * 0.40),
        (size * 0.60, size * 0.55),
        (size * 0.55, size * 0.72),
        (size * 0.48, size * 0.68),
        (size * 0.45, size * 0.50),
    ]
    draw.polygon([(int(x), int(y)) for x, y in af_points], fill=continent_color)

    # Asia (simplified)
    asia_points = [
        (size * 0.60, size * 0.18),
        (size * 0.85, size * 0.22),
        (size * 0.90, size * 0.35),
        (size * 0.82, size * 0.48),
        (size * 0.70, size * 0.45),
        (size * 0.62, size * 0.35),
    ]
    draw.polygon([(int(x), int(y)) for x, y in asia_points], fill=continent_color)

    # Australia (simplified)
    au_points = [
        (size * 0.78, size * 0.62),
        (size * 0.88, size * 0.60),
        (size * 0.90, size * 0.72),
        (size * 0.82, size * 0.78),
        (size * 0.75, size * 0.72),
    ]
    draw.polygon([(int(x), int(y)) for x, y in au_points], fill=continent_color)

    # Draw map pins
    pin_positions = [
        (size * 0.22, size * 0.32, (220, 60, 60)),  # USA - red
        (size * 0.20, size * 0.22, (60, 140, 220)),  # Canada - blue
        (size * 0.26, size * 0.68, (255, 180, 50)),  # South America - orange/yellow
    ]

    for px, py, color in pin_positions:
        draw_map_pin(draw, int(px), int(py), int(size * 0.08), color)

    # Round corners
    img = add_rounded_corners(img, int(size * 0.22))

    img.save(output_path, "PNG")
    print(f"Created Footprint icon: {output_path}")


def draw_map_pin(draw, cx, cy, size, color):
    """Draw a location pin marker."""
    # Pin body (teardrop shape)
    pin_top = cy - size
    pin_bottom = cy + int(size * 0.3)

    # Draw pin shadow
    shadow_offset = size // 8
    draw.ellipse(
        [
            cx - size // 3 + shadow_offset,
            cy + shadow_offset,
            cx + size // 3 + shadow_offset,
            cy + size // 2 + shadow_offset,
        ],
        fill=(0, 0, 0, 80),
    )

    # Draw teardrop pin shape
    # Upper circle part
    draw.ellipse([cx - size // 2, pin_top, cx + size // 2, pin_top + size], fill=color)

    # Lower triangle part
    triangle = [
        (cx - size // 2 + size // 8, cy - size // 4),
        (cx + size // 2 - size // 8, cy - size // 4),
        (cx, pin_bottom + size // 3),
    ]
    draw.polygon(triangle, fill=color)

    # Inner white circle
    inner_size = size // 3
    draw.ellipse(
        [
            cx - inner_size,
            pin_top + size // 2 - inner_size,
            cx + inner_size,
            pin_top + size // 2 + inner_size,
        ],
        fill=(255, 255, 255),
    )


def add_rounded_corners(img, radius):
    """Add rounded corners to an image."""
    # Create a mask for rounded corners
    mask = Image.new("L", img.size, 0)
    draw = ImageDraw.Draw(mask)
    draw.rounded_rectangle([(0, 0), img.size], radius=radius, fill=255)

    # Apply mask
    result = Image.new("RGBA", img.size, (0, 0, 0, 0))
    result.paste(img, mask=mask)
    return result


def main():
    # Ensure Pillow is available
    script_dir = os.path.dirname(os.path.abspath(__file__))

    # Generate Powder Chaser icon
    snow_icon_path = os.path.join(
        script_dir, "..", "ios", "fastlane", "metadata", "app_icon.png"
    )
    os.makedirs(os.path.dirname(snow_icon_path), exist_ok=True)
    create_powder_chaser_icon(snow_icon_path)

    # Also generate for footprint if this script is run from snow repo
    footprint_path = os.path.join(
        script_dir,
        "..",
        "..",
        "footprint",
        "ios",
        "fastlane",
        "metadata",
        "app_icon.png",
    )
    if os.path.exists(os.path.dirname(os.path.dirname(footprint_path))):
        os.makedirs(os.path.dirname(footprint_path), exist_ok=True)
        create_footprint_icon(footprint_path)


if __name__ == "__main__":
    main()
