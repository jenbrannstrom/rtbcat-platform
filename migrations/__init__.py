"""Database migrations for RTBcat Creative Intelligence.

This module provides a simple migration system for SQLite databases.
Migrations are SQL files in the migrations/ directory named with a
numeric prefix (e.g., 001_initial.sql, 002_add_import_history.sql).

Usage:
    # Run all pending migrations
    python -m migrations.runner

    # Check migration status
    python -m migrations.runner --status

    # Create a new migration
    python -m migrations.runner --create "add_new_table"
"""
