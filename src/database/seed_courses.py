from src.database.session import SessionLocal

from src.database.models.course import Course



def seed_demo_courses():

    db = SessionLocal()

    demo_titles = [
        "تنظیم و میکس حرفه‌ای",
        "آهنگسازی",
    ]

    existing = (
        db.query(Course)
        .filter(Course.title.in_(demo_titles))
        .count()
    )

    if existing:
        print("Demo courses already exist - skipping.")
        db.close()
        return

    courses = [

        Course(
            title="تنظیم و میکس حرفه‌ای",
            description="آموزش کامل تنظیم، میکس و مسترینگ",
            price=5000000,
        ),


        Course(
            title="آهنگسازی",
            description="هارمونی، ملودی و ساختار آهنگ",
            price=3000000,
        ),

    ]

    db.add_all(courses)
    db.commit()
    db.close()

    print("Demo courses added")


if __name__ == "__main__":
    seed_demo_courses()
