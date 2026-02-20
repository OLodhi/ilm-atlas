"""Create an admin user. Run from project root: python scripts/create_admin.py"""
import asyncio
import sys

sys.path.insert(0, "backend")

from app.database import async_session
from app.models.db import Base, User
from app.services.auth.password import hash_password


async def main():
    email = input("Admin email: ").strip().lower()
    password = input("Admin password: ").strip()
    name = input("Display name (optional): ").strip() or None

    if len(password) < 8:
        print("Error: Password must be at least 8 characters.")
        return

    async with async_session() as session:
        user = User(
            email=email,
            password_hash=hash_password(password),
            display_name=name,
            role="admin",
            email_verified=True,
            is_active=True,
        )
        session.add(user)
        await session.commit()
        print(f"Admin user created: {email} (id: {user.id})")


if __name__ == "__main__":
    asyncio.run(main())
