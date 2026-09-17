"""
Set thumbnail URLs on products so ArtistYar site can show package covers.

Usage (from project root, with DB env configured):

    python -m scripts.set_product_thumbnails

Edit THUMBNAILS below with public image URLs (Supabase Storage, CDN, etc.).
Safe to re-run: only updates matching titles.
"""

from __future__ import annotations

from src.database.session import SessionLocal
from src.database.models.course import Course

# Map exact product title -> public image URL
THUMBNAILS: dict[str, str] = {
    # "راه‌یار": "https://YOUR_CDN/rahyar-cover.jpg",
    # "تئوری موسیقی": "https://YOUR_CDN/theory-cover.jpg",
    # "آرتیست‌یار": "https://YOUR_CDN/artistyar-cover.jpg",
}


def main() -> None:
    if not THUMBNAILS:
        print("No THUMBNAILS configured. Edit scripts/set_product_thumbnails.py first.")
        return

    db = SessionLocal()
    updated = 0
    try:
        for title, url in THUMBNAILS.items():
            product = db.query(Course).filter(Course.title == title).first()
            if not product:
                print(f"Skip (not found): {title}")
                continue
            product.thumbnail = url.strip() or None
            updated += 1
            print(f"Updated thumbnail: {title}")
        db.commit()
        print(f"Done. {updated} product(s) updated.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
