from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


images = sorted(Path("/private/tmp").glob("usps_all-*.png"))
out = Path("/private/tmp/usps_tracking_contact_sheet.png")

font = ImageFont.load_default()
crops = []
for index, path in enumerate(images, start=1):
    im = Image.open(path).convert("RGB")
    w, h = im.size
    crop = im.crop((int(w * 0.08), int(h * 0.78), int(w * 0.95), int(h * 0.88)))
    crop = crop.resize((crop.width // 2, crop.height // 2))
    label_h = 26
    panel = Image.new("RGB", (crop.width, crop.height + label_h), "white")
    draw = ImageDraw.Draw(panel)
    draw.text((8, 6), f"Page {index}", fill="red", font=font)
    panel.paste(crop, (0, label_h))
    crops.append(panel)

cols = 2
rows = (len(crops) + cols - 1) // cols
cell_w = max(c.width for c in crops)
cell_h = max(c.height for c in crops)
sheet = Image.new("RGB", (cols * cell_w, rows * cell_h), "white")
for idx, crop in enumerate(crops):
    x = (idx % cols) * cell_w
    y = (idx // cols) * cell_h
    sheet.paste(crop, (x, y))

sheet.save(out)
print(out)
