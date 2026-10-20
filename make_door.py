import os
from PIL import Image, ImageDraw, ImageFont

os.makedirs("templates", exist_ok=True)
img = Image.new("RGB", (400, 400), color="#08070f")
draw = ImageDraw.Draw(img)

# Draw an ancient stone archway / locked door motif
draw.rectangle([80, 50, 320, 380], outline="#d4af37", width=4)
draw.rectangle([100, 80, 300, 380], fill="#110e1f", outline="#b366ff", width=2)
# Keyhole / Lock motif
draw.polygon([(200, 180), (212, 215), (188, 215)], fill="#d4af37")
draw.ellipse([190, 210, 210, 235], fill="#d4af37")
draw.line([200, 235, 200, 280], fill="#d4af37", width=5)

img.save("templates/door.webp", "WEBP", quality=85)
print("✨ Generated templates/door.webp successfully!")