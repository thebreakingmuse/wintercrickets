import json
import os
import subprocess

try:
  from PIL import Image, ImageOps

  PILLOW_AVAILABLE = True
except ImportError:
  PILLOW_AVAILABLE = False

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PORTALS_DIR = os.path.join(BASE_DIR, "portals")
TEMPLATES_DIR = os.path.join(BASE_DIR, "templates")
JSON_PATH = os.path.join(BASE_DIR, "branches.json")

VALID_THEMES = ["nocturnal", "cyber", "celestial", "oceanic", "rose"]
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".gif"}

MAX_FULL_DIMENSION = 1920
FULL_WEBP_QUALITY = 82
GRID_THUMB_SIZE = (400, 400)
GRID_THUMB_QUALITY = 78

PORTAL_PRESETS = {
    "1": {
        "name": "Esoteric & Arcane",
        "prefix": "arcane",
        "default_theme": "celestial",
    },
    "2": {
        "name": "Natural & Organic",
        "prefix": "natural",
        "default_theme": "oceanic",
    },
    "3": {
        "name": "Fantasy & Love",
        "prefix": "love",
        "default_theme": "rose",
    },
    "4": {
        "name": "Ancient Locked Door",
        "prefix": "door",
        "default_theme": "nocturnal",
    },
}

REALM_BACKGROUNDS = {
    "1": {
        "id": "cosmos",
        "name": "Obsidian & Violet Nebula (Default Cosmic Void)",
    },
    "2": {
        "id": "verdant",
        "name": "Bioluminescent Canopy (Subterranean Emerald & Spores)",
    },
    "3": {
        "id": "ember",
        "name": "Alchemical Sanctuary (Red Ochre, Copper & Floating Embers)",
    },
    "4": {"id": "abyss", "name": "Abyssal Trench (Deep Sapphire & Aqua Glow)"},
    "5": {
        "id": "astral",
        "name": "Silver Eclipse (Celestial Monochrome & Diamond Stars)",
    },
}

FILAMENT_STYLES = {
    "1": {"id": "standard", "name": "Standard Glowing Gradient"},
    "2": {"id": "vine", "name": "Twisting Organic Vine"},
    "3": {"id": "tendril", "name": "Dual-Strand Braided Tendril"},
}


def load_branches():
  if not os.path.exists(JSON_PATH):
    return []
  try:
    with open(JSON_PATH, "r", encoding="utf-8") as f:
      return json.load(f)
  except json.JSONDecodeError as e:
    print(f"\n[!] Error reading branches.json: {e}")
    return []


def save_branches(branches):
  with open(JSON_PATH, "w", encoding="utf-8") as f:
    json.dump(branches, f, indent=2, ensure_ascii=False)


def suggest_angle(existing_angles):
  if not existing_angles:
    return -25
  candidates = [
      -25,
      25,
      155,
      -155,
      -65,
      65,
      115,
      -115,
      0,
      180,
      -90,
      90,
      -45,
      45,
      135,
      -135,
  ]
  for c in candidates:
    if all(abs((c - a + 180) % 360 - 180) >= 22 for a in existing_angles):
      return c
  return (existing_angles[-1] + 35) % 360 - 180


def find_template_file(prefix):
  if not os.path.exists(TEMPLATES_DIR):
    return None
  for f in sorted(os.listdir(TEMPLATES_DIR)):
    name, ext = os.path.splitext(f)
    if ext.lower() in IMAGE_EXTENSIONS and name.lower().startswith(
        prefix.lower()
    ):
      return f"templates/{f}"
  return None


def optimize_full_images(folder_path, folder_name):
  if not PILLOW_AVAILABLE:
    return
  files = sorted([
      f
      for f in os.listdir(folder_path)
      if os.path.isfile(os.path.join(folder_path, f))
  ])
  for filename in files:
    name, ext = os.path.splitext(filename)
    ext_lower = ext.lower()
    if ext_lower not in IMAGE_EXTENSIONS or ext_lower == ".gif":
      continue
    src_path = os.path.join(folder_path, filename)
    dest_path = os.path.join(folder_path, f"{name}.webp")
    try:
      with Image.open(src_path) as im:
        if getattr(im, "is_animated", False):
          continue
        width, height = im.size
        file_size_kb = os.path.getsize(src_path) / 1024.0
        if (
            ext_lower == ".webp"
            and max(width, height) <= MAX_FULL_DIMENSION
            and file_size_kb <= 650
        ):
          continue
        im = ImageOps.exif_transpose(im)
        if im.mode not in ("RGB", "RGBA"):
          im = im.convert("RGB")
        if max(im.size) > MAX_FULL_DIMENSION:
          im.thumbnail(
              (MAX_FULL_DIMENSION, MAX_FULL_DIMENSION), Image.Resampling.LANCZOS
          )
        im.save(dest_path, "WEBP", quality=FULL_WEBP_QUALITY, method=4)
      if ext_lower != ".webp" and os.path.exists(dest_path):
        os.remove(src_path)
    except Exception as e:
      print(f"    [!] Could not optimize {filename}: {e}")


def generate_grid_thumbnails(folder_path, folder_name, image_filenames):
  if not PILLOW_AVAILABLE:
    return [f"portals/{folder_name}/{img}" for img in image_filenames]
  thumbs_dir = os.path.join(folder_path, "grid_thumbs")
  os.makedirs(thumbs_dir, exist_ok=True)
  grid_thumb_paths = []
  expected_thumbs = set()
  for img_name in image_filenames:
    src_path = os.path.join(folder_path, img_name)
    base_name = os.path.splitext(img_name)[0]
    thumb_filename = f"{base_name}.webp"
    expected_thumbs.add(thumb_filename)
    dest_path = os.path.join(thumbs_dir, thumb_filename)
    if not os.path.exists(dest_path) or os.path.getmtime(
        src_path
    ) > os.path.getmtime(dest_path):
      try:
        with Image.open(src_path) as im:
          im = ImageOps.exif_transpose(im)
          if im.mode not in ("RGB", "RGBA"):
            im = im.convert("RGB")
          thumb_im = ImageOps.fit(im, GRID_THUMB_SIZE, Image.Resampling.LANCZOS)
          thumb_im.save(dest_path, "WEBP", quality=GRID_THUMB_QUALITY, method=4)
      except Exception:
        grid_thumb_paths.append(f"portals/{folder_name}/{img_name}")
        continue
    grid_thumb_paths.append(
        f"portals/{folder_name}/grid_thumbs/{thumb_filename}"
    )
  for existing_thumb in os.listdir(thumbs_dir):
    if existing_thumb not in expected_thumbs:
      try:
        os.remove(os.path.join(thumbs_dir, existing_thumb))
      except OSError:
        pass
  return grid_thumb_paths


def get_folder_media(folder_path, folder_name):
  optimize_full_images(folder_path, folder_name)
  files = sorted([
      f
      for f in os.listdir(folder_path)
      if os.path.isfile(os.path.join(folder_path, f))
  ])
  images = [
      f for f in files if os.path.splitext(f)[1].lower() in IMAGE_EXTENSIONS
  ]
  if not images:
    return None, [], []
  custom_thumb = None
  for img in images:
    if "thumb" in img.lower():
      custom_thumb = f"portals/{folder_name}/{img}"
      break
  gallery_files = [img for img in images if "thumb" not in img.lower()]
  if not gallery_files:
    gallery_files = images
  photos = [f"portals/{folder_name}/{img}" for img in gallery_files]
  grid_thumbs = generate_grid_thumbnails(
      folder_path, folder_name, gallery_files
  )
  return custom_thumb, photos, grid_thumbs


def choose_slice(branches):
  slice_map = {}
  for b in branches:
    s_name = b.get("slice") or "Prime Cosmos"
    s_bg = b.get("slice_bg") or "cosmos"
    if s_name not in slice_map:
      slice_map[s_name] = s_bg
  if not slice_map:
    slice_map["Prime Cosmos"] = "cosmos"

  existing_slices = list(slice_map.keys())
  print("\n    Select 3D Portal Disk (Slice):")
  for idx, s_name in enumerate(existing_slices, 1):
    print(f"      [{idx}] {s_name} (Realm: {slice_map[s_name]})")
  new_idx = len(existing_slices) + 1
  print(f"      [{new_idx}] + Create a New 3D Disk / Slice")

  choice = input("    Choice [1]: ").strip() or "1"
  if choice.isdigit() and 1 <= int(choice) <= len(existing_slices):
    chosen_name = existing_slices[int(choice) - 1]
    return chosen_name, slice_map[chosen_name]

  new_name = (
      input("    Enter Name for New 3D Disk [Subterranean Realm]: ").strip()
      or "Subterranean Realm"
  )
  print("\n    Select Background Aesthetic for this Disk:")
  for key, bg in REALM_BACKGROUNDS.items():
    print(f"      [{key}] {bg['name']}")
  bg_choice = input("    Realm Choice [2]: ").strip() or "2"
  chosen_bg = REALM_BACKGROUNDS.get(bg_choice, REALM_BACKGROUNDS["2"])["id"]
  return new_name, chosen_bg


def choose_portal_style(custom_thumb, photos):
  if custom_thumb:
    return custom_thumb, "nocturnal"
  print("\n    Select a Portal Ring Thumbnail:")
  for key, preset in PORTAL_PRESETS.items():
    found = find_template_file(preset["prefix"])
    status = f"({found})" if found else "(place in templates/ folder)"
    print(f"      [{key}] {preset['name']} {status}")
  print("      [5] Use first photo in this gallery folder")
  choice = input("    Choice [1]: ").strip() or "1"
  if choice in PORTAL_PRESETS:
    preset = PORTAL_PRESETS[choice]
    template_path = find_template_file(preset["prefix"])
    if template_path:
      return template_path, preset["default_theme"]
    else:
      fallback = f"templates/{preset['prefix']}.webp"
      return fallback, preset["default_theme"]
  return photos[0], "nocturnal"


def choose_filament_style():
  print("\n    Select Connective Filament Style:")
  for key, style in FILAMENT_STYLES.items():
    print(f"      [{key}] {style['name']}")
  choice = input("    Choice [1]: ").strip() or "1"
  return FILAMENT_STYLES.get(choice, FILAMENT_STYLES["1"])["id"]


def git_sync():
  print("\n" + "=" * 60)
  print("  GIT & NETLIFY DEPLOYMENT SYNC")
  print("=" * 60)
  if not os.path.exists(os.path.join(BASE_DIR, ".git")):
    return
  status = subprocess.run(
      ["git", "status", "--porcelain"],
      cwd=BASE_DIR,
      capture_output=True,
      text=True,
  )
  if not status.stdout.strip():
    print("✓ Git working tree is already clean.")
  choice = (
      input("\nPush latest updates to GitHub & Netlify now? [Y/n]: ")
      .strip()
      .lower()
  )
  if choice not in ("", "y", "yes"):
    return
  commit_msg = (
      input(
          "Commit message (press Enter for 'Sync portal network updates'): "
      ).strip()
      or "Sync portal network updates"
  )
  try:
    subprocess.run(["git", "add", "."], cwd=BASE_DIR, check=True)
    subprocess.run(["git", "commit", "-m", commit_msg], cwd=BASE_DIR, check=True)
    subprocess.run(["git", "push", "origin", "main"], cwd=BASE_DIR, check=True)
    print("\n✨ SUCCESS! Changes pushed to GitHub.")
  except subprocess.CalledProcessError as e:
    print(f"\n[!] Git command failed (exit code {e.returncode}).")


def main():
  print("\n" + "=" * 60)
  print("  ESOTERIC PORTAL NETWORK — 3D DISK & FOLDER SYNC")
  print("=" * 60 + "\n")
  os.makedirs(PORTALS_DIR, exist_ok=True)
  os.makedirs(TEMPLATES_DIR, exist_ok=True)
  branches = load_branches()
  folders = sorted([
      f
      for f in os.listdir(PORTALS_DIR)
      if os.path.isdir(os.path.join(PORTALS_DIR, f)) and not f.startswith(".")
  ])
  changes_made = False

  kept_branches = []
  for b in branches:
    bid = b.get("id")
    if bid not in folders:
      changes_made = True
    else:
      if "slice" not in b:
        b["slice"] = "Prime Cosmos"
        b["slice_bg"] = "cosmos"
        changes_made = True
      if "filament" not in b:
        b["filament"] = "standard"
        changes_made = True
      kept_branches.append(b)
  branches = kept_branches

  existing_map = {b["id"]: b for b in branches}

  for folder in folders:
    folder_path = os.path.join(PORTALS_DIR, folder)
    custom_thumb, photos, grid_thumbs = get_folder_media(folder_path, folder)
    if not photos:
      continue

    if folder in existing_map:
      branch = existing_map[folder]
      updated = False
      if branch.get("photos") != photos:
        branch["photos"] = photos
        updated = True
      if branch.get("grid_thumbs") != grid_thumbs:
        branch["grid_thumbs"] = grid_thumbs
        updated = True
      if updated:
        changes_made = True
    else:
      print(
          f"\n[+] NEW PORTAL FOLDER DETECTED: '{folder}' ({len(photos)} photos)"
      )

      # 1. Select 3D Disk / Slice and Realm Background
      slice_name, slice_bg = choose_slice(branches)
      slice_angles = [
          b.get("angle", 0)
          for b in branches
          if b.get("slice", "Prime Cosmos") == slice_name
      ]

      default_title = folder.replace("-", " ").replace("_", " ").title()
      title = (
          input(f"\n    Display Title [{default_title}]: ").strip()
          or default_title
      )
      subtitle = (
          input("    Subtitle [Gallery & Archive]: ").strip()
          or "Gallery & Archive"
      )
      password = (
          input(
              "    Access Keyword/Password (leave blank for public access): "
          )
          .strip()
          .lower()
      )

      thumb, suggested_theme = choose_portal_style(custom_thumb, photos)
      theme = (
          input(f"    Glow Theme [{suggested_theme}]: ").strip().lower()
          or suggested_theme
      )
      filament = choose_filament_style()

      sug_angle = suggest_angle(slice_angles)
      angle_in = input(
          f"\n    Radial Angle on '{slice_name}' in degrees [{sug_angle}]: "
      ).strip()
      angle = int(angle_in) if angle_in.lstrip("-").isdigit() else sug_angle
      dist_in = input("    Distance from center in px [340]: ").strip()
      distance = int(dist_in) if dist_in.isdigit() else 340

      new_branch = {
          "id": folder,
          "title": title,
          "subtitle": subtitle,
          "slice": slice_name,
          "slice_bg": slice_bg,
          "theme": theme,
          "filament": filament,
          "angle": angle,
          "distance": distance,
          "thumbnail": thumb,
          "photos": photos,
          "grid_thumbs": grid_thumbs,
          "password": password,
      }
      branches.append(new_branch)
      changes_made = True
      print(f"    ✓ Added '{title}' to disk '{slice_name}' in branches.json")

  if changes_made:
    save_branches(branches)
    print("\n✓ branches.json updated successfully!")
  git_sync()


if __name__ == "__main__":
  main()