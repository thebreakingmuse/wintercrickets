import os
import json
from pathlib import Path

try:
    from PIL import Image, ImageOps
    HAS_PIL = True
except ImportError:
    HAS_PIL = False
    print("⚠️ Pillow not installed. Run 'pip install Pillow' for automatic WebP & thumbnail generation.")

BASE_DIR = Path(__file__).resolve().parent
PORTALS_DIR = BASE_DIR / "portals"
BRANCHES_FILE = BASE_DIR / "branches.json"

REALM_BGS = ["cosmos", "nyc", "verdant", "ember", "abyss", "astral", "wilderness"]
THEMES = ["nocturnal", "cyber", "celestial", "oceanic", "rose"]
FILAMENT_STYLES = ["standard", "vine", "tendril", "suspension", "grid", "gothic"]

MAX_FULL_DIM = 1920
FULL_WEBP_QUALITY = 82
THUMB_DIM = (400, 400)
THUMB_WEBP_QUALITY = 78

VALID_SOURCE_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tiff"}


def load_existing_branches():
    if BRANCHES_FILE.exists():
        try:
            with open(BRANCHES_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, list):
                    return data
        except Exception as e:
            print(f"⚠️ Could not parse existing branches.json: {e}")
    return []


def process_portal_images(portal_dir: Path, folder_id: str):
    thumbs_dir = portal_dir / "grid_thumbs"
    thumbs_dir.mkdir(exist_ok=True)

    if HAS_PIL:
        for file_path in sorted(portal_dir.iterdir()):
            if file_path.is_dir():
                continue
            ext = file_path.suffix.lower()
            if ext not in VALID_SOURCE_EXTS:
                continue

            stem_clean = (
                file_path.stem.lower()
                .replace(" ", "-")
                .replace("_", "-")
            )
            target_webp = portal_dir / f"{stem_clean}.webp"
            target_thumb = thumbs_dir / f"{stem_clean}.webp"

            # Convert non-webp or missing webp
            if not target_webp.exists() or file_path != target_webp:
                try:
                    with Image.open(file_path) as im:
                        im = ImageOps.exif_transpose(im).convert("RGB")
                        im.thumbnail((MAX_FULL_DIM, MAX_FULL_DIM), Image.Resampling.LANCZOS)
                        im.save(target_webp, "WEBP", quality=FULL_WEBP_QUALITY, method=6)
                    if file_path != target_webp:
                        file_path.unlink()
                    print(f"  ✓ Converted full WebP: {target_webp.name}")
                except Exception as e:
                    print(f"  ⚠️ Failed converting {file_path.name}: {e}")
                    continue

            # Ensure 400x400 square grid thumbnail exists
            if not target_thumb.exists() and target_webp.exists():
                try:
                    with Image.open(target_webp) as im:
                        im = ImageOps.exif_transpose(im).convert("RGB")
                        thumb = ImageOps.fit(im, THUMB_DIM, Image.Resampling.LANCZOS)
                        thumb.save(target_thumb, "WEBP", quality=THUMB_WEBP_QUALITY, method=6)
                    print(f"  ✓ Generated 400x400 thumb: grid_thumbs/{target_thumb.name}")
                except Exception as e:
                    print(f"  ⚠️ Failed generating thumb for {target_webp.name}: {e}")

    photos = []
    grid_thumbs = []
    for webp_file in sorted(portal_dir.glob("*.webp")):
        rel_photo = f"portals/{folder_id}/{webp_file.name}"
        thumb_candidate = thumbs_dir / webp_file.name
        rel_thumb = (
            f"portals/{folder_id}/grid_thumbs/{webp_file.name}"
            if thumb_candidate.exists()
            else rel_photo
        )
        photos.append(rel_photo)
        grid_thumbs.append(rel_thumb)

    return photos, grid_thumbs


def suggest_open_angle(existing_angles):
    candidates = [-25, 25, 155, -155, -65, 65, 115, -115, 0, 180, -90, 90, -45, 45, 135, -135]
    for c in candidates:
        if all(abs(((c - a + 540) % 360) - 180) >= 24 for a in existing_angles):
            return c
    return ((existing_angles[-1] + 35) % 360) - 180 if existing_angles else -25


def sync_portals():
    PORTALS_DIR.mkdir(exist_ok=True)
    existing_list = load_existing_branches()
    existing_map = {b.get("id"): b for b in existing_list if b.get("id")}

    updated_branches = []

    # 1. Preserve existing portals and refresh their local photos if the folder exists locally
    for branch in existing_list:
        pid = branch.get("id")
        if not pid:
            continue
        p_dir = PORTALS_DIR / pid
        if p_dir.exists() and p_dir.is_dir():
            print(f"🔄 Scanning portal folder: portals/{pid}/")
            disk_photos, disk_thumbs = process_portal_images(p_dir, pid)

            # Keep cross-portal linked photos while syncing local folder photos
            existing_photos = branch.get("photos", [])
            existing_thumbs = branch.get("grid_thumbs", [])
            cross_linked_photos = [
                (p, existing_thumbs[i] if i < len(existing_thumbs) else p)
                for i, p in enumerate(existing_photos)
                if not p.startswith(f"portals/{pid}/")
            ]

            merged_photos = list(disk_photos)
            merged_thumbs = list(disk_thumbs)
            for cp, ct in cross_linked_photos:
                if cp not in merged_photos:
                    merged_photos.append(cp)
                    merged_thumbs.append(ct)

            if merged_photos:
                branch["photos"] = merged_photos
                branch["grid_thumbs"] = merged_thumbs

        # Validate slice_bg, theme, filament
        if branch.get("slice_bg") not in REALM_BGS:
            branch["slice_bg"] = "cosmos"
        if branch.get("theme") not in THEMES:
            branch["theme"] = "nocturnal"
        if branch.get("filament") not in FILAMENT_STYLES:
            branch["filament"] = "standard"

        # Fix missing or broken thumbnail fallback automatically
        thumb = branch.get("thumbnail", "")
        if not thumb or (not (BASE_DIR / thumb).exists() and branch.get("grid_thumbs")):
            if branch.get("grid_thumbs"):
                branch["thumbnail"] = branch["grid_thumbs"][0]

        updated_branches.append(branch)

    # 2. Discover brand-new folders dropped into portals/
    known_ids = {b["id"] for b in updated_branches}
    for folder in sorted(PORTALS_DIR.iterdir()):
        if not folder.is_dir() or folder.name.startswith("."):
            continue
        folder_id = folder.name
        if folder_id in known_ids:
            continue

        print(f"✨ Discovered new portal folder: portals/{folder_id}/")
        photos, grid_thumbs = process_portal_images(folder, folder_id)
        if not photos:
            print(f"  ℹ️ Skipping empty folder portals/{folder_id}/ (no images found)")
            continue

        prime_angles = [
            b.get("angle", 0)
            for b in updated_branches
            if b.get("slice", "Prime Cosmos") == "Prime Cosmos"
        ]
        new_portal = {
            "id": folder_id,
            "title": folder_id.replace("-", " ").replace("_", " ").title(),
            "subtitle": "Gallery & Archive",
            "slice": "Prime Cosmos",
            "slice_bg": "cosmos",
            "theme": THEMES[len(updated_branches) % len(THEMES)],
            "filament": "standard",
            "angle": suggest_open_angle(prime_angles),
            "distance": 340,
            "thumbnail": grid_thumbs[0] if grid_thumbs else photos[0],
            "photos": photos,
            "grid_thumbs": grid_thumbs,
            "password": ""
        }
        updated_branches.append(new_portal)

    # 3. Ensure Prime Cosmos portals are positioned first in branches.json
    updated_branches.sort(key=lambda b: 0 if b.get("slice", "Prime Cosmos") == "Prime Cosmos" else 1)

    with open(BRANCHES_FILE, "w", encoding="utf-8") as f:
        json.dump(updated_branches, f, indent=2)

    print(f"\n✅ Synced {len(updated_branches)} portal(s) to branches.json!")


if __name__ == "__main__":
    sync_portals()