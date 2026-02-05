"""Inference logging for API requests."""

import aiosqlite
import json
import logging
from datetime import datetime
from typing import Optional, Dict, Any
from pathlib import Path

from config.settings import get_settings

logger = logging.getLogger(__name__)


class InferenceLogger:
    """Logger for inference requests and responses."""
    
    def __init__(self, db_path: Optional[str] = None):
        """Initialize inference logger.
        
        Args:
            db_path: Path to SQLite database (uses settings if None)
        """
        settings = get_settings()
        self.db_path = db_path or settings.inference_log_db_path
        
        # Ensure directory exists
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        
        # Cache initialization state to avoid repeated DB schema checks
        self._db_initialized = False
    
    async def _init_db(self):
        """Initialize database schema."""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                CREATE TABLE IF NOT EXISTS inference_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    request_id TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    method TEXT,
                    path TEXT,
                    status_code INTEGER,
                    duration REAL,
                    error TEXT,
                    question TEXT,
                    answer TEXT,
                    metadata TEXT,
                    UNIQUE(request_id)
                )
            """)
            await db.execute("""
                CREATE INDEX IF NOT EXISTS idx_request_id ON inference_logs(request_id)
            """)
            await db.execute("""
                CREATE INDEX IF NOT EXISTS idx_timestamp ON inference_logs(timestamp)
            """)
            await db.commit()
            
            # Migrate existing tables: Add question and answer columns if they don't exist
            await self._migrate_schema(db)
    
    async def _migrate_schema(self, db):
        """Migrate existing database schema to add new columns.
        
        Args:
            db: Database connection
        """
        try:
            # Check if question column exists
            cursor = await db.execute("PRAGMA table_info(inference_logs)")
            columns = await cursor.fetchall()
            column_names = [col[1] for col in columns]
            
            # Add question column if it doesn't exist
            if 'question' not in column_names:
                await db.execute("ALTER TABLE inference_logs ADD COLUMN question TEXT")
                logger.info("Added 'question' column to inference_logs table")
            
            # Add answer column if it doesn't exist
            if 'answer' not in column_names:
                await db.execute("ALTER TABLE inference_logs ADD COLUMN answer TEXT")
                logger.info("Added 'answer' column to inference_logs table")
            
            await db.commit()
        except Exception as e:
            logger.warning(f"Schema migration warning (may be expected for new databases): {e}")
            # Don't raise - migration failures are not critical
    
    async def _ensure_db_initialized(self):
        """Ensure database is initialized (only once per instance).
        
        This method caches the initialization state to avoid repeated
        CREATE TABLE/INDEX checks on every operation.
        """
        if not self._db_initialized:
            try:
                await self._init_db()
                self._db_initialized = True
            except Exception as e:
                logger.error(f"Failed to initialize inference logger database: {e}", exc_info=True)
                # Re-raise to let caller handle it
                raise
    
    async def log_request(
        self,
        request_id: str,
        method: str,
        path: str,
        status_code: int,
        duration: float,
        metadata: Optional[Dict[str, Any]] = None,
        question: Optional[str] = None,
        answer: Optional[str] = None
    ):
        """Log an inference request.
        
        Args:
            request_id: Request ID (must not be None or empty)
            method: HTTP method
            path: Request path
            status_code: Response status code
            duration: Request duration in seconds
            metadata: Additional metadata
            question: User question/query (for chat endpoints)
            answer: Agent response/answer (for chat endpoints)
            
        Raises:
            ValueError: If request_id is None or empty
            Exception: If database operation fails
        """
        # Validate request_id
        if not request_id or request_id.strip() == "":
            raise ValueError("request_id cannot be None or empty")
        
        try:
            await self._ensure_db_initialized()
            
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute("""
                    INSERT OR REPLACE INTO inference_logs
                    (request_id, timestamp, method, path, status_code, duration, question, answer, metadata)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    request_id,
                    datetime.utcnow().isoformat(),
                    method,
                    path,
                    status_code,
                    duration,
                    question,
                    answer,
                    json.dumps(metadata or {})
                ))
                await db.commit()
        except Exception as e:
            logger.error(
                f"Failed to log request {request_id} to database: {e}",
                exc_info=True
            )
            # Re-raise to let caller handle it (middleware will catch and log)
            raise
    
    async def log_error(
        self,
        request_id: str,
        method: str,
        path: str,
        error: str,
        duration: float,
        metadata: Optional[Dict[str, Any]] = None,
        question: Optional[str] = None,
        answer: Optional[str] = None
    ):
        """Log an inference error.
        
        Args:
            request_id: Request ID (must not be None or empty)
            method: HTTP method
            path: Request path
            error: Error message
            duration: Request duration in seconds
            metadata: Additional metadata
            question: User question/query (for chat endpoints)
            answer: Agent response/answer (may be None for errors)
            
        Raises:
            ValueError: If request_id is None or empty
            Exception: If database operation fails
        """
        # Validate request_id
        if not request_id or request_id.strip() == "":
            raise ValueError("request_id cannot be None or empty")
        
        try:
            await self._ensure_db_initialized()
            
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute("""
                    INSERT OR REPLACE INTO inference_logs
                    (request_id, timestamp, method, path, status_code, duration, error, question, answer, metadata)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    request_id,
                    datetime.utcnow().isoformat(),
                    method,
                    path,
                    500,
                    duration,
                    error,
                    question,
                    answer,
                    json.dumps(metadata or {})
                ))
                await db.commit()
        except Exception as e:
            logger.error(
                f"Failed to log error for request {request_id} to database: {e}",
                exc_info=True
            )
            # Re-raise to let caller handle it (middleware will catch and log)
            raise
    
    async def get_log(self, request_id: str) -> Optional[Dict[str, Any]]:
        """Get log entry by request ID.
        
        Args:
            request_id: Request ID
            
        Returns:
            Log entry or None if not found or on error
            
        Raises:
            Exception: If database operation fails
        """
        try:
            await self._ensure_db_initialized()
            
            async with aiosqlite.connect(self.db_path) as db:
                db.row_factory = aiosqlite.Row
                async with db.execute("""
                    SELECT * FROM inference_logs WHERE request_id = ?
                """, (request_id,)) as cursor:
                    row = await cursor.fetchone()
                    if row:
                        return dict(row)
            return None
        except Exception as e:
            logger.error(
                f"Failed to get log for request {request_id} from database: {e}",
                exc_info=True
            )
            # Re-raise to let caller handle it
            raise
    
    async def get_logs(
        self,
        limit: int = 100,
        offset: int = 0
    ) -> list[Dict[str, Any]]:
        """Get recent logs.
        
        Args:
            limit: Maximum number of logs
            offset: Offset for pagination
            
        Returns:
            List of log entries (empty list on error)
            
        Raises:
            Exception: If database operation fails
        """
        try:
            await self._ensure_db_initialized()
            
            async with aiosqlite.connect(self.db_path) as db:
                db.row_factory = aiosqlite.Row
                async with db.execute("""
                    SELECT * FROM inference_logs
                    ORDER BY timestamp DESC
                    LIMIT ? OFFSET ?
                """, (limit, offset)) as cursor:
                    rows = await cursor.fetchall()
                    return [dict(row) for row in rows]
        except Exception as e:
            logger.error(
                f"Failed to get logs from database: {e}",
                exc_info=True
            )
            # Re-raise to let caller handle it
            raise
