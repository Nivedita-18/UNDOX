import argparse

from sqlalchemy import select

from app.database import SessionLocal
from app.models import User


def main():
    parser = argparse.ArgumentParser(
        description="Promote an existing UNDOX user to ADMIN."
    )

    parser.add_argument(
        "email",
        help="Email address of the existing registered user."
    )

    args = parser.parse_args()
    email = args.email.strip().lower()

    db = SessionLocal()

    try:
        user = db.scalar(
            select(User).where(User.email == email)
        )

        if user is None:
            print("User not found. Register the account first.")
            return

        if user.role == "ADMIN":
            print(f"{email} is already an ADMIN.")
            return

        user.role = "ADMIN"
        db.commit()

        print(f"Successfully promoted {email} to ADMIN.")

    except Exception:
        db.rollback()
        raise

    finally:
        db.close()


if __name__ == "__main__":
    main()
