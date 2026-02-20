---
name: python-database-guidelines
description: SQLAlchemy ORM and Alembic migration patterns
version: 1.0.0
triggers:
  - sqlalchemy
  - alembic
  - database
  - migration
  - orm
  - model
  - query
---

# Python Database Guidelines

## Overview

This skill provides patterns for SQLAlchemy ORM usage, async database operations, and Alembic migrations. Use this when working with databases in Python projects.

## Quick Reference

| Pattern | When to Use | Example |
|---------|-------------|---------|
| Model | Define database tables | `class User(Base)` |
| Repository | Data access layer | `UserRepository.get_by_id()` |
| Session | Database transactions | `async with session.begin()` |
| Migration | Schema changes | `alembic revision --autogenerate` |

## Project Configuration

<!-- CUSTOMIZE START -->
| Setting | Default | Your Value |
|---------|---------|------------|
| ORM | SQLAlchemy 2.0 | CHANGE_ME |
| Database | PostgreSQL | CHANGE_ME |
| Async | Yes | CHANGE_ME |
| Migration Tool | Alembic | CHANGE_ME |
<!-- CUSTOMIZE END -->

## Core Patterns

### Pattern 1: Model Definition

```python
# ✅ CORRECT: Well-structured SQLAlchemy model
from sqlalchemy import String, DateTime, ForeignKey, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from datetime import datetime

class Base(DeclarativeBase):
    """Base class for all models."""
    pass

class TimestampMixin:
    """Mixin for created_at and updated_at timestamps."""
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now()
    )

class User(Base, TimestampMixin):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(100))
    hashed_password: Mapped[str] = mapped_column(String(255))
    is_active: Mapped[bool] = mapped_column(default=True)

    # Relationships
    posts: Mapped[list["Post"]] = relationship(back_populates="author")

    def __repr__(self) -> str:
        return f"<User(id={self.id}, email={self.email})>"

class Post(Base, TimestampMixin):
    __tablename__ = "posts"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(200))
    content: Mapped[str] = mapped_column()
    author_id: Mapped[int] = mapped_column(ForeignKey("users.id"))

    # Relationships
    author: Mapped["User"] = relationship(back_populates="posts")
```

### Pattern 2: Async Session Setup

```python
# ✅ CORRECT: Async session configuration
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from contextlib import asynccontextmanager

DATABASE_URL = "postgresql+asyncpg://user:pass@localhost/db"

engine = create_async_engine(
    DATABASE_URL,
    echo=False,  # Set True for SQL logging
    pool_size=5,
    max_overflow=10,
)

async_session_factory = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)

@asynccontextmanager
async def get_async_session():
    """Get async database session."""
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
```

### Pattern 3: Repository Pattern

```python
# ✅ CORRECT: Repository with async operations
from sqlalchemy import select, update, delete
from sqlalchemy.ext.asyncio import AsyncSession
from app.models import User

class UserRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_id(self, user_id: int) -> User | None:
        """Get user by ID."""
        result = await self.session.execute(
            select(User).where(User.id == user_id)
        )
        return result.scalar_one_or_none()

    async def get_by_email(self, email: str) -> User | None:
        """Get user by email."""
        result = await self.session.execute(
            select(User).where(User.email == email)
        )
        return result.scalar_one_or_none()

    async def get_all(self, skip: int = 0, limit: int = 100) -> list[User]:
        """Get all users with pagination."""
        result = await self.session.execute(
            select(User)
            .offset(skip)
            .limit(limit)
            .order_by(User.created_at.desc())
        )
        return list(result.scalars().all())

    async def create(self, **kwargs) -> User:
        """Create a new user."""
        user = User(**kwargs)
        self.session.add(user)
        await self.session.flush()
        await self.session.refresh(user)
        return user

    async def update(self, user_id: int, **kwargs) -> User | None:
        """Update user by ID."""
        await self.session.execute(
            update(User)
            .where(User.id == user_id)
            .values(**kwargs)
        )
        return await self.get_by_id(user_id)

    async def delete(self, user_id: int) -> bool:
        """Delete user by ID."""
        result = await self.session.execute(
            delete(User).where(User.id == user_id)
        )
        return result.rowcount > 0
```

### Pattern 4: Complex Queries

```python
# ✅ CORRECT: Complex queries with joins and aggregations
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload, joinedload

class PostRepository:
    async def get_with_author(self, post_id: int) -> Post | None:
        """Get post with author eagerly loaded."""
        result = await self.session.execute(
            select(Post)
            .options(joinedload(Post.author))
            .where(Post.id == post_id)
        )
        return result.scalar_one_or_none()

    async def get_by_author(self, author_id: int) -> list[Post]:
        """Get all posts by author."""
        result = await self.session.execute(
            select(Post)
            .where(Post.author_id == author_id)
            .order_by(Post.created_at.desc())
        )
        return list(result.scalars().all())

    async def get_post_counts_by_author(self) -> list[tuple[int, int]]:
        """Get post counts grouped by author."""
        result = await self.session.execute(
            select(Post.author_id, func.count(Post.id))
            .group_by(Post.author_id)
        )
        return list(result.all())

    async def search(self, query: str) -> list[Post]:
        """Search posts by title."""
        result = await self.session.execute(
            select(Post)
            .where(Post.title.ilike(f"%{query}%"))
            .order_by(Post.created_at.desc())
            .limit(20)
        )
        return list(result.scalars().all())
```

### Pattern 5: Alembic Migrations

```python
# alembic/env.py - Async configuration
from alembic import context
from sqlalchemy.ext.asyncio import create_async_engine
from app.models import Base
from app.config import DATABASE_URL

target_metadata = Base.metadata

def run_migrations_offline():
    context.configure(
        url=DATABASE_URL,
        target_metadata=target_metadata,
        literal_binds=True,
    )
    with context.begin_transaction():
        context.run_migrations()

async def run_migrations_online():
    engine = create_async_engine(DATABASE_URL)
    async with engine.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await engine.dispose()

def do_run_migrations(connection):
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()
```

```bash
# Common Alembic commands
alembic revision --autogenerate -m "Add users table"
alembic upgrade head
alembic downgrade -1
alembic history
```

## Anti-Patterns

### Don't: N+1 Queries

```python
# ❌ BAD: N+1 query problem
posts = await session.execute(select(Post))
for post in posts.scalars():
    print(post.author.name)  # Each access triggers a query!

# ✅ GOOD: Eager loading
posts = await session.execute(
    select(Post).options(joinedload(Post.author))
)
for post in posts.scalars():
    print(post.author.name)  # No additional queries
```

### Don't: Raw SQL Without Parameterization

```python
# ❌ BAD: SQL injection risk
query = f"SELECT * FROM users WHERE email = '{email}'"

# ✅ GOOD: Parameterized query
result = await session.execute(
    select(User).where(User.email == email)
)
```

### Don't: Long-Running Transactions

```python
# ❌ BAD: Session open during slow operations
async with get_async_session() as session:
    user = await repo.get_by_id(1)
    await send_email(user.email)  # Slow! Session still open
    await repo.update(user.id, notified=True)

# ✅ GOOD: Separate transactions
async with get_async_session() as session:
    user = await repo.get_by_id(1)

await send_email(user.email)  # Outside transaction

async with get_async_session() as session:
    await repo.update(user.id, notified=True)
```

## Migration Best Practices

### DO

- Always review autogenerated migrations
- Test migrations on a copy of production data
- Keep migrations small and focused
- Use descriptive migration names

### DON'T

- Manually edit migration history
- Skip migrations in production
- Put data transformations in schema migrations
- Delete old migration files

## Resources

| Topic | Link |
|-------|------|
| Models | [mdc:resources/models.md] |
| Queries | [mdc:resources/queries.md] |
| Migrations | [mdc:resources/migrations.md] |
| Async Patterns | [mdc:resources/async-patterns.md] |
