"""
Migration script to migrate conversation data from JSON files to SQLite database.

Usage:
    python -m backend.migration

This script:
1. Reads all JSON files from data/conversations/
2. Creates SQLite database tables
3. Migrates all conversations and messages
4. Archives JSON files to data/conversations_backup/
5. Verifies data integrity

Run this once during Phase 1 deployment.
"""

import json
import os
import shutil
from pathlib import Path
from datetime import datetime
from sqlalchemy.orm import Session

from .database import sync_engine, Base, get_sync_db
from .models import Conversation, Message


def migrate_json_to_sqlite():
    """
    Main migration function.
    """
    print("=" * 60)
    print("Cove Database Migration: JSON → SQLite")
    print("=" * 60)

    # Create all tables
    print("\n[1/5] Creating database tables...")
    Base.metadata.create_all(bind=sync_engine)
    print("✓ Tables created successfully")

    # Find all JSON conversation files
    conversations_dir = Path("data/conversations")
    if not conversations_dir.exists():
        print(f"\n⚠ No conversations directory found at {conversations_dir}")
        print("Migration complete (nothing to migrate)")
        return

    json_files = list(conversations_dir.glob("*.json"))
    print(f"\n[2/5] Found {len(json_files)} conversation files to migrate")

    if len(json_files) == 0:
        print("Migration complete (nothing to migrate)")
        return

    # Migrate each conversation
    print("\n[3/5] Migrating conversations...")
    migrated_count = 0
    skipped_count = 0

    with next(get_sync_db()) as db:
        for json_file in json_files:
            try:
                with open(json_file, 'r', encoding='utf-8') as f:
                    conv_data = json.load(f)

                # Check if already migrated
                existing = db.query(Conversation).filter_by(id=conv_data["id"]).first()
                if existing:
                    print(f"  ⊙ Skipping {conv_data['id']} (already exists)")
                    skipped_count += 1
                    continue

                # Create conversation record
                conversation = Conversation(
                    id=conv_data["id"],
                    created_at=datetime.fromisoformat(conv_data["created_at"].replace('Z', '+00:00')),
                    title=conv_data.get("title", "New Conversation"),
                    workspace=conv_data.get("workspace", "General"),  # Default for old conversations
                )
                db.add(conversation)

                # Migrate messages
                message_count = 0
                for msg_data in conv_data.get("messages", []):
                    if msg_data["role"] == "user":
                        # User message - store content directly
                        message = Message(
                            conversation_id=conversation.id,
                            role="user",
                            content=msg_data["content"],
                            created_at=conversation.created_at,  # Approximate timestamp
                        )
                        db.add(message)
                        message_count += 1
                    else:
                        # Assistant message - serialize stage data as JSON
                        assistant_content = json.dumps({
                            "stage1": msg_data.get("stage1", []),
                            "stage2": msg_data.get("stage2", []),
                            "stage3": msg_data.get("stage3", {}),
                        })
                        message = Message(
                            conversation_id=conversation.id,
                            role="assistant",
                            content=assistant_content,
                            created_at=conversation.created_at,
                        )
                        db.add(message)
                        message_count += 1

                db.commit()
                print(f"  ✓ Migrated {conv_data['id']}: {message_count} messages")
                migrated_count += 1

            except Exception as e:
                print(f"  ✗ Error migrating {json_file.name}: {e}")
                db.rollback()
                continue

    print(f"\n✓ Migration complete: {migrated_count} conversations migrated, {skipped_count} skipped")

    # Verify data integrity
    print("\n[4/5] Verifying data integrity...")
    with next(get_sync_db()) as db:
        total_conversations = db.query(Conversation).count()
        total_messages = db.query(Message).count()
        print(f"  ✓ Database contains {total_conversations} conversations with {total_messages} messages")

    # Archive JSON files
    print("\n[5/5] Archiving JSON files...")
    backup_dir = Path("data/conversations_backup")
    backup_dir.mkdir(parents=True, exist_ok=True)

    for json_file in json_files:
        backup_path = backup_dir / json_file.name
        shutil.copy2(json_file, backup_path)

    print(f"  ✓ Backed up {len(json_files)} files to {backup_dir}")
    print("\n⚠ JSON files have been backed up but NOT deleted.")
    print("  You can manually delete data/conversations/*.json after verifying the migration.")

    print("\n" + "=" * 60)
    print("Migration complete!")
    print("=" * 60)


if __name__ == "__main__":
    migrate_json_to_sqlite()
