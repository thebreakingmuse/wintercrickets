import os
import json
import subprocess

# Ensure paths always resolve relative to where this script lives
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PORTALS_DIR = os.path.join(BASE_DIR, "portals")
JSON_PATH = os.path.join(BASE_DIR, "branches.json")

# Optional Pillow support for automatic WebP image optimization
try:
    from PIL import Image
    PILLOW_AVAILABLE = True
except ImportError:
    PILLOW_AVAILABLE = False

THEMES = {
    "1": ("nocturnal", "Nocturnal Mountain (Moonlit Indigo & Firefly Cyan)"),
    "2": ("cyber", "Tech & Cybernetic (Matrix Teal & Neon Magenta)"),
    "3": ("celestial", "Celestial Archive (Starlight Gold & Solar Amber)"),
    "4": ("oceanic", "Oceanic & Voyage (Bioluminescent Aqua & Deep Trench Blue)")
}

VALID_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".gif"}


def optimize_image(filepath, max_size=1920, quality=80):
    """
    If Pillow is installed, converts large static JPG/PNG images to optimized WebP
    for fast web loading while leaving animated GIFs/WebPs untouched.
    """
    if not PILLOW_AVAILABLE:
        return filepath

    ext = os.path.splitext(filepath)[1].lower()
    if ext in {".gif", ".webp"}:
        return filepath  # Leave existing WebPs and animated GIFs intact

    try:
        with Image.open(filepath) as img:
            # Resize if larger than max_size on longest side
            if max(img.size) > max_size:
                img.thumbnail((max_size, max_size), Image.Resampling.LANCZOS)

            webp_path = os.path.splitext(filepath)[0] + ".webp"
            img.save(webp_path, "WEBP", quality=quality)
        os.remove(filepath)
        print(f"  [Optimized] Converted {os.path.basename(filepath)} -> {os.path.basename(webp_path)}")
        return webp_path
    except Exception as e:
        print(f"  [Notice] Could not optimize {os.path.basename(filepath)}: {e}")
        return filepath


def load_branches():
    if os.path.exists(JSON_PATH):
        try:
            with open(JSON_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except json.JSONDecodeError:
            print("[Warning] branches.json was empty or corrupted. Starting fresh.")
    return []


def suggest_angle(existing_branches):
    """
    Suggests an open angle (in degrees) so new portals don't overlap existing ones.
    Alternates nicely around the circle.
    """
    preset_angles = [-25, 25, 155, -155, -65, 65, 115, -115, 0, 180, -90, 90]
    used_angles = {b.get("angle") for b in existing_branches if b.get("angle") is not None}
    for angle in preset_angles:
        if angle not in used_angles:
            return angle
    return (len(existing_branches) * 40) % 360 - 180


def scan_folder_media(folder_path, folder_name):
    """
    Scans a portal subfolder for photos, thumbnails (thumb.*), and custom ligaments (ligament.*).
    Returns relative web paths for branches.json.
    """
    files = sorted(os.listdir(folder_path))
    photos = []
    thumbnail = ""
    ligament_gif = ""

    for fname in files:
        if fname.startswith("."):
            continue
        full_path = os.path.join(folder_path, fname)
        if not os.path.isfile(full_path):
            continue

        ext = os.path.splitext(fname)[1].lower()
        if ext not in VALID_EXTS:
            continue

        base_lower = os.path.splitext(fname)[0].lower()

        # Check for dedicated ligament sprite
        if base_lower.startswith("ligament"):
            ligament_gif = f"portals/{folder_name}/{fname}"
            continue

        # Check for dedicated portal thumbnail
        if base_lower.startswith("thumb") or base_lower.startswith("portal"):
            thumbnail = f"portals/{folder_name}/{fname}"
            continue

        # Optimize standard gallery photo if Pillow is available
        optimized_full_path = optimize_image(full_path)
        final_fname = os.path.basename(optimized_full_path)
        web_path = f"portals/{folder_name}/{final_fname}"
        photos.append(web_path)

    # If no dedicated thumb.* was found, use the first photo in the folder
    if not thumbnail and photos:
        thumbnail = photos[0]

    return thumbnail, ligament_gif, photos


def main():
    print("=" * 60)
    print("  ESOTERIC PORTAL NETWORK — FOLDER SCANNER & SYNC")
    print("=" * 60)

    if not os.path.exists(PORTALS_DIR):
        os.makedirs(PORTALS_DIR)
        print(f"Created '{PORTALS_DIR}' directory.")
        print("Drop your photo album folders inside 'portals/' and run this script again!")
        return

    branches = load_branches()
    existing_by_id = {b["id"]: b for b in branches if "id" in b}

    subfolders = sorted([
        f for f in os.listdir(PORTALS_DIR)
        if os.path.isdir(os.path.join(PORTALS_DIR, f)) and not f.startswith(".")
    ])

    if not subfolders:
        print("No album folders found inside 'portals/'. Drop a folder in and re-run!")
        return

    changes_made = False

    for folder_name in subfolders:
        folder_path = os.path.join(PORTALS_DIR, folder_name)
        thumbnail, ligament_gif, photos = scan_folder_media(folder_path, folder_name)

        if not photos and not thumbnail:
            print(f"\n[Skipping] '{folder_name}' (No images found inside)")
            continue

        # CASE 1: Existing portal -> automatically sync any newly added photos
        if folder_name in existing_by_id:
            branch = existing_by_id[folder_name]
            if branch.get("photos") != photos or branch.get("thumbnail") != thumbnail or branch.get("customLigamentGif") != ligament_gif:
                branch["photos"] = photos
                if thumbnail:
                    branch["thumbnail"] = thumbnail
                if ligament_gif:
                    branch["customLigamentGif"] = ligament_gif
                changes_made = True
                print(f"\n[Updated] Synced media list for existing portal: '{branch.get('title', folder_name)}' ({len(photos)} photos)")
            continue

        # CASE 2: Brand new folder detected -> Interactive Theme & Metadata Prompt
        print("\n" + "-" * 60)
        print(f"✨ NEW PORTAL FOLDER DETECTED: '{folder_name}' ({len(photos)} photos)")
        print("-" * 60)

        default_title = folder_name.replace("-", " ").replace("_", " ").title()
        title = input(f"Enter Portal Title [default: {default_title}]: ").strip() or default_title
        subtitle = input("Enter Subtitle (e.g., 'Hiking & Starlight') [optional]: ").strip()

        print("\nChoose Connective Ligament Theme:")
        for key, (code, desc) in THEMES.items():
            print(f"  [{key}] {desc}")
        theme_choice = input("Select Theme (1-4) [default: 1 - nocturnal]: ").strip()
        theme_code = THEMES.get(theme_choice, THEMES["1"])[0]

        default_angle = suggest_angle(branches)
        angle_input = input(f"Enter Branch Angle in degrees (-180 to 180) [default: {default_angle}]: ").strip()
        try:
            angle = int(angle_input) if angle_input else default_angle
        except ValueError:
            angle = default_angle

        dist_input = input("Enter Branch Distance in pixels [default: 340]: ").strip()
        try:
            distance = int(dist_input) if dist_input else 340
        except ValueError:
            distance = 340

        new_branch = {
            "id": folder_name,
            "title": title,
            "subtitle": subtitle if subtitle else theme_code.title(),
            "theme": theme_code,
            "angle": angle,
            "distance": distance,
            "thumbnail": thumbnail,
            "customLigamentGif": ligament_gif,
            "photos": photos
        }

        branches.append(new_branch)
        changes_made = True
        print(f"✅ Added '{title}' with '{theme_code}' ligament at {angle}°!")

    if changes_made:
        with open(JSON_PATH, "w", encoding="utf-8") as f:
            json.dump(branches, f, indent=2)
        print("\n" + "=" * 60)
        print(f"💾 Saved updated portal network to: {JSON_PATH}")
        print("=" * 60)

        # Optional Git Auto-Push for Netlify Continuous Deployment
        git_dir = os.path.join(BASE_DIR, ".git")
        if os.path.exists(git_dir):
            push_choice = input("\nGit repository detected. Commit & push to Netlify/GitHub now? (y/n) [n]: ").strip().lower()
            if push_choice == "y":
                try:
                    subprocess.run(["git", "add", "."], cwd=BASE_DIR, check=True)
                    subprocess.run(["git", "commit", "-m", "Sync new portal branches and media"], cwd=BASE_DIR, check=True)
                    subprocess.run(["git", "push"], cwd=BASE_DIR, check=True)
                    print("🚀 Successfully pushed to GitHub! Netlify will deploy your changes shortly.")
                except Exception as e:
                    print(f"⚠️ Git push encountered an issue: {e}")
    else:
        print("\nEverything is already up to date! No new folders or photo changes detected.")


if __name__ == "__main__":
    main()
