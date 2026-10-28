import json
import os
import subprocess
from pathlib import Path
from PIL import Image, ImageOps

# --- Configuration ---
PORTALS_DIR = Path("portals")
BRANCHES_FILE = Path("branches.json")
MAX_FULL_DIM = 1920
FULL_WEBP_QUALITY = 82
THUMB_DIM = 400
THUMB_WEBP_QUALITY = 78

VALID_RAW_EXTS = {".jpg", ".jpeg", ".png", ".bmp", ".tiff", ".webp"}

THEMES = ["nocturnal", "cyber", "celestial", "oceanic", "rose"]
FILAMENTS = ["standard", "vine", "tendril", "suspension", "grid"]
REALM_BGS = ["cosmos", "nyc", "verdant", "ember", "abyss", "astral"]


def run_cmd(cmd_list):
    """Run a shell command and return (returncode, stdout, stderr)."""
    result = subprocess.run(cmd_list, capture_output=True, text=True)
    return result.returncode, result.stdout.strip(), result.stderr.strip()


def git_auto_pull():
    """Pull latest web uploads from thebreakingmuse/wintercrickets before scanning."""
    print("\n✦ Syncing latest changes from GitHub (thebreakingmuse/wintercrickets)...")
    code, out, err = run_cmd(["git", "pull", "--rebase", "--autostash", "origin", "main"])
    if code == 0:
        print(f"  ✓ Local workspace is up to date with GitHub. ({out or 'No new remote changes'})")
    else:
        print(f"  ⚠️ Note during git pull: {err or out}")
        print("  Continuing with local portal scan...")


def load_branches():
    if BRANCHES_FILE.exists():
        try:
            with open(BRANCHES_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"⚠️ Could not parse {BRANCHES_FILE}: {e}")
    return []


def save_branches(branches):
    with open(BRANCHES_FILE, "w", encoding="utf-8") as f:
        json.dump(branches, f, indent=2, ensure_ascii=False)
    print(f"✓ Updated {BRANCHES_FILE} ({len(branches)} portals total).")


def suggest_open_angle(branches, slice_name, exclude_id=None):
    used = [
        b.get("angle", 0)
        for b in branches
        if (b.get("slice") or "Prime Cosmos") == slice_name and b.get("id") != exclude_id
    ]
    if not used:
        return -25
    candidates = [-25, 25, 155, -155, -65, 65, 115, -115, 0, 180, -90, 90, -45, 45, 135, -135]
    for c in candidates:
        if all(abs(((c - a + 540) % 360) - 180) >= 24 for a in used):
            return c
    return ((used[-1] + 35) % 360) - 180


def make_grid_thumb(img, thumb_path):
    """Create a 400x400 center-cropped WebP thumbnail."""
    thumb_path.parent.mkdir(parents=True, exist_ok=True)
    cropped = ImageOps.fit(img, (THUMB_DIM, THUMB_DIM), method=Image.Resampling.LANCZOS)
    cropped.save(thumb_path, "WEBP", quality=THUMB_WEBP_QUALITY)


def process_portal_folder(folder_path):
    """
    Fast-scan a portal folder:
    - If a file is ALREADY .webp and its grid_thumbs/<name>.webp exists, skip Pillow completely!
    - If a raw image (.jpg/.png) is found, convert to 1920px .webp, create 400x400 thumb, and remove raw file.
    """
    thumbs_dir = folder_path / "grid_thumbs"
    thumbs_dir.mkdir(parents=True, exist_ok=True)

    converted_count = 0
    skipped_count = 0

    all_files = sorted([p for p in folder_path.iterdir() if p.is_file()])

    for file_path in all_files:
        ext = file_path.suffix.lower()
        if ext not in VALID_RAW_EXTS:
            continue

        clean_stem = file_path.stem.lower().replace(" ", "-")
        target_webp = folder_path / f"{clean_stem}.webp"
        target_thumb = thumbs_dir / f"{clean_stem}.webp"

        # FAST PATH: Already a .webp with matching filename AND grid_thumb exists -> instant skip!
        if ext == ".webp" and file_path == target_webp and target_thumb.exists():
            skipped_count += 1
            continue

        # Otherwise, open with Pillow to convert/resize or generate missing thumbnail
        try:
            with Image.open(file_path) as raw_img:
                img = ImageOps.exif_transpose(raw_img)
                if img.mode not in ("RGB", "RGBA"):
                    img = img.convert("RGB")

                # Save full 1920px max WebP if needed
                if ext != ".webp" or file_path != target_webp:
                    w, h = img.size
                    if max(w, h) > MAX_FULL_DIM:
                        img.thumbnail((MAX_FULL_DIM, MAX_FULL_DIM), Image.Resampling.LANCZOS)
                    img.save(target_webp, "WEBP", quality=FULL_WEBP_QUALITY)

                # Generate 400x400 grid thumbnail if missing or new
                if not target_thumb.exists() or ext != ".webp":
                    make_grid_thumb(img, target_thumb)

            # Remove original non-webp file or un-normalized filename
            if file_path != target_webp and file_path.exists():
                file_path.unlink()

            converted_count += 1
        except Exception as e:
            print(f"  ⚠️ Error processing {file_path.name}: {e}")

    # Collect final sorted .webp paths
    final_webps = sorted([p for p in folder_path.glob("*.webp") if p.is_file()])
    photos_list = [f"portals/{folder_path.name}/{p.name}" for p in final_webps]
    thumbs_list = [f"portals/{folder_path.name}/grid_thumbs/{p.name}" for p in final_webps]

    if converted_count > 0:
        print(f"  ⚡ [{folder_path.name}] Converted {converted_count} new photo(s), fast-skipped {skipped_count} existing.")
    else:
        print(f"  ✓ [{folder_path.name}] Fast-skipped {skipped_count} already-optimized WebP photo(s).")

    return photos_list, thumbs_list


def sync_all_portals():
    PORTALS_DIR.mkdir(exist_ok=True)
    branches = load_branches()
    branch_map = {b["id"]: b for b in branches if "id" in b}

    subfolders = sorted([d for d in PORTALS_DIR.iterdir() if d.is_dir() and not d.name.startswith(".")])

    for folder in subfolders:
        folder_id = folder.name
        photos, grid_thumbs = process_portal_folder(folder)

        if not photos:
            continue

        if folder_id in branch_map:
            # Update photo lists while preserving all existing settings
            entry = branch_map[folder_id]
            entry["photos"] = photos
            entry["grid_thumbs"] = grid_thumbs
            if not entry.get("thumbnail"):
                entry["thumbnail"] = "templates/arcane.webp"
        else:
            # Brand-new portal folder discovered locally
            print(f"\n✨ New portal folder detected: 'portals/{folder_id}'")
            default_title = folder_id.replace("-", " ").replace("_", " ").title()
            title = input(f"  Enter Display Title [{default_title}]: ").strip() or default_title
            slice_name = input("  Enter 3D Disk Name [Prime Cosmos]: ").strip() or "Prime Cosmos"
            slice_bg = input(f"  Enter Realm Background ({'/'.join(REALM_BGS)}) [cosmos]: ").strip() or "cosmos"
            theme = input(f"  Enter Glow Theme ({'/'.join(THEMES)}) [nocturnal]: ").strip() or "nocturnal"
            filament = input(f"  Enter Filament Style ({'/'.join(FILAMENTS)}) [standard]: ").strip() or "standard"
            password = input("  Optional Password Lock (Enter for public): ").strip().lower()

            angle = suggest_open_angle(branches, slice_name, exclude_id=folder_id)

            new_entry = {
                "id": folder_id,
                "title": title,
                "subtitle": "Gallery & Archive",
                "slice": slice_name,
                "slice_bg": slice_bg if slice_bg in REALM_BGS else "cosmos",
                "theme": theme if theme in THEMES else "nocturnal",
                "filament": filament if filament in FILAMENTS else "standard",
                "angle": angle,
                "distance": 340,
                "thumbnail": "templates/arcane.webp",
                "photos": photos,
                "grid_thumbs": grid_thumbs,
                "password": password
            }
            branches.append(new_entry)
            branch_map[folder_id] = new_entry

    save_branches(branches)
    return branches


def git_push_changes():
    choice = input("\n🚀 Push all updates to GitHub (thebreakingmuse/wintercrickets) now? [Y/n]: ").strip().lower()
    if choice not in ("", "y", "yes"):
        print("Skipped GitHub push.")
        return

    print("Staging files...")
    run_cmd(["git", "add", "."])

    status_code, status_out, _ = run_cmd(["git", "status", "--porcelain"])
    if not status_out:
        print("✓ No new file changes to commit. Everything is already in sync!")
        return

    run_cmd(["git", "commit", "-m", "Sync portals & studio updates"])

    print("Pulling any last-second remote updates with rebase...")
    run_cmd(["git", "pull", "--rebase", "origin", "main"])

    print("Pushing to https://github.com/thebreakingmuse/wintercrickets.git ...")
    code, out, err = run_cmd(["git", "push", "origin", "main"])
    if code == 0:
        print("✨ Successfully pushed to wintercrickets! Netlify (darklyvibrant) is now deploying depthofsparkle.life.")
    else:
        print(f"⚠️ Push encountered an issue:\n{err or out}")


if __name__ == "__main__":
    print("====================================================")
    print("  ESOTERIC PORTAL SYNC — wintercrickets Fast Engine ")
    print("====================================================")
    git_auto_pull()
    sync_all_portals()
    git_push_changes()