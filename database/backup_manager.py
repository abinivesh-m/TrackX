"""
backup_manager.py

Database backup and restore functionality for TrackX.

Provides safe backup and restore operations for the SQLite database
without breaking existing functionality.
"""

import os
import shutil
from datetime import datetime
from pathlib import Path
from config import DB_PATH_STR, RESULTS_DIR


class BackupManager:
    """Manages database backup and restore operations."""
    
    def __init__(self, db_path: str = DB_PATH_STR):
        self.db_path = db_path
        self.backup_dir = RESULTS_DIR / "backups"
        self.backup_dir.mkdir(exist_ok=True)
    
    def create_backup(self, backup_name: str = None) -> str:
        """
        Create a backup of the current database.
        
        Args:
            backup_name: Optional custom name for the backup. If not provided,
                        uses timestamp-based name.
        
        Returns:
            Path to the created backup file.
        """
        if not os.path.exists(self.db_path):
            raise FileNotFoundError(f"Database file not found: {self.db_path}")
        
        if backup_name is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_name = f"trackx_backup_{timestamp}.db"
        
        backup_path = self.backup_dir / backup_name
        
        # Copy the database file
        shutil.copy2(self.db_path, backup_path)
        
        return str(backup_path)
    
    def restore_backup(self, backup_path: str) -> bool:
        """
        Restore database from a backup file.
        
        Args:
            backup_path: Path to the backup file to restore from.
        
        Returns:
            True if restore was successful, False otherwise.
        """
        if not os.path.exists(backup_path):
            raise FileNotFoundError(f"Backup file not found: {backup_path}")
        
        # Create a backup of current database before restoring
        try:
            self.create_backup("pre_restore_backup.db")
        except:
            pass  # If current DB doesn't exist, that's fine
        
        # Restore from backup
        shutil.copy2(backup_path, self.db_path)
        
        return True
    
    def list_backups(self) -> list:
        """
        List all available backup files.
        
        Returns:
            List of backup file information dicts.
        """
        backups = []
        
        if not self.backup_dir.exists():
            return backups
        
        for backup_file in self.backup_dir.glob("*.db"):
            stat = backup_file.stat()
            backups.append({
                "name": backup_file.name,
                "path": str(backup_file),
                "size": stat.st_size,
                "created": datetime.fromtimestamp(stat.st_ctime),
                "modified": datetime.fromtimestamp(stat.st_mtime)
            })
        
        # Sort by modification time (newest first)
        backups.sort(key=lambda x: x["modified"], reverse=True)
        
        return backups
    
    def delete_backup(self, backup_path: str) -> bool:
        """
        Delete a backup file.
        
        Args:
            backup_path: Path to the backup file to delete.
        
        Returns:
            True if deletion was successful, False otherwise.
        """
        try:
            os.remove(backup_path)
            return True
        except Exception as e:
            print(f"Failed to delete backup: {e}")
            return False
    
    def cleanup_old_backups(self, keep_count: int = 5) -> int:
        """
        Remove old backups, keeping only the most recent ones.
        
        Args:
            keep_count: Number of most recent backups to keep.
        
        Returns:
            Number of backups deleted.
        """
        backups = self.list_backups()
        
        if len(backups) <= keep_count:
            return 0
        
        # Delete older backups
        deleted_count = 0
        for backup in backups[keep_count:]:
            if self.delete_backup(backup["path"]):
                deleted_count += 1
        
        return deleted_count


if __name__ == "__main__":
    # Test the backup manager
    manager = BackupManager()
    
    print("Creating backup...")
    backup_path = manager.create_backup()
    print(f"Backup created: {backup_path}")
    
    print("\nListing backups:")
    backups = manager.list_backups()
    for backup in backups[:5]:
        print(f"  {backup['name']} ({backup['size']} bytes) - {backup['modified']}")
    
    print(f"\nTotal backups: {len(backups)}")
    
    # Cleanup old backups (keep only 3 most recent)
    print("\nCleaning up old backups (keeping 3 most recent)...")
    deleted = manager.cleanup_old_backups(keep_count=3)
    print(f"Deleted {deleted} old backup(s)")
