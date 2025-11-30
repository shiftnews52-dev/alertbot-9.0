"""
database.py - Работа с базой данных
"""
import time
import asyncio
import logging
from typing import List
from datetime import datetime, timedelta
import aiosqlite

from config import DB_PATH

logger = logging.getLogger(__name__)

# ==================== SQL SCHEMA ====================
INIT_SQL = """
PRAGMA journal_mode=WAL;
PRAGMA synchronous=NORMAL;
PRAGMA cache_size=10000;
PRAGMA temp_store=MEMORY;

CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY,
    username TEXT,
    created_at INTEGER DEFAULT (strftime('%s', 'now')),
    subscription_until INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS tracked_pairs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    pair TEXT NOT NULL,
    added_at INTEGER DEFAULT (strftime('%s', 'now')),
    UNIQUE(user_id, pair),
    FOREIGN KEY (user_id) REFERENCES users(user_id)
);

CREATE TABLE IF NOT EXISTS signals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    pair TEXT NOT NULL,
    side TEXT NOT NULL,
    price REAL NOT NULL,
    confidence INTEGER NOT NULL,
    sent_at INTEGER DEFAULT (strftime('%s', 'now')),
    FOREIGN KEY (user_id) REFERENCES users(user_id)
);

CREATE INDEX IF NOT EXISTS idx_tracked_pairs_user ON tracked_pairs(user_id);
CREATE INDEX IF NOT EXISTS idx_tracked_pairs_pair ON tracked_pairs(pair);
CREATE INDEX IF NOT EXISTS idx_signals_user ON signals(user_id);
CREATE INDEX IF NOT EXISTS idx_signals_pair ON signals(pair);
CREATE INDEX IF NOT EXISTS idx_signals_sent ON signals(sent_at);
"""

# ==================== БАЗА ДАННЫХ ====================

async def init_db():
    """Инициализация базы данных"""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.executescript(INIT_SQL)
        await db.commit()
    logger.info("✅ Database initialized")

# ==================== ПОЛЬЗОВАТЕЛИ ====================

async def add_user(user_id: int, username: str = None):
    """Добавить пользователя"""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT OR IGNORE INTO users (user_id, username) VALUES (?, ?)",
            (user_id, username)
        )
        await db.commit()

async def get_user_subscription(user_id: int) -> int:
    """Получить дату окончания подписки (timestamp)"""
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT subscription_until FROM users WHERE user_id = ?",
            (user_id,)
        ) as cursor:
            row = await cursor.fetchone()
            return row[0] if row else 0

async def update_subscription(user_id: int, days: int):
    """Обновить подписку (добавить дни)"""
    current_time = int(time.time())
    
    # Получаем текущую подписку
    current_sub = await get_user_subscription(user_id)
    
    # Если подписка активна, добавляем к ней, иначе от текущего времени
    if current_sub > current_time:
        new_sub = current_sub + (days * 86400)
    else:
        new_sub = current_time + (days * 86400)
    
    async with aiosqlite.connect(DB_PATH) as db:
        # Добавляем пользователя если его нет
        await db.execute(
            "INSERT OR IGNORE INTO users (user_id) VALUES (?)",
            (user_id,)
        )
        # Обновляем подписку
        await db.execute(
            "UPDATE users SET subscription_until = ? WHERE user_id = ?",
            (new_sub, user_id)
        )
        await db.commit()
    
    logger.info(f"✅ User {user_id} subscription updated: +{days} days")

async def is_user_subscribed(user_id: int) -> bool:
    """Проверить активна ли подписка"""
    sub_until = await get_user_subscription(user_id)
    current_time = int(time.time())
    return sub_until > current_time

# ==================== ОТСЛЕЖИВАЕМЫЕ ПАРЫ ====================

async def get_user_pairs(user_id: int) -> List[str]:
    """Получить все пары пользователя"""
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT pair FROM tracked_pairs WHERE user_id = ? ORDER BY added_at",
            (user_id,)
        ) as cursor:
            rows = await cursor.fetchall()
            return [row[0] for row in rows]

async def add_tracked_pair(user_id: int, pair: str) -> bool:
    """Добавить пару для отслеживания"""
    try:
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute(
                "INSERT INTO tracked_pairs (user_id, pair) VALUES (?, ?)",
                (user_id, pair)
            )
            await db.commit()
        return True
    except aiosqlite.IntegrityError:
        return False  # Уже есть

async def remove_tracked_pair(user_id: int, pair: str) -> bool:
    """Удалить пару из отслеживания"""
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "DELETE FROM tracked_pairs WHERE user_id = ? AND pair = ?",
            (user_id, pair)
        )
        await db.commit()
        return cursor.rowcount > 0

async def get_all_tracked_pairs() -> List[str]:
    """Получить все уникальные отслеживаемые пары"""
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT DISTINCT pair FROM tracked_pairs") as cursor:
            rows = await cursor.fetchall()
            return [row[0] for row in rows]

async def get_pairs_with_users():
    """Получить пары с пользователями которые их отслеживают"""
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            """
            SELECT tp.pair, tp.user_id 
            FROM tracked_pairs tp
            JOIN users u ON tp.user_id = u.user_id
            WHERE u.subscription_until > strftime('%s', 'now')
            """
        ) as cursor:
            rows = await cursor.fetchall()
            return [{"pair": row[0], "user_id": row[1]} for row in rows]

# ==================== СИГНАЛЫ ====================

async def count_signals_today(pair: str) -> int:
    """Подсчитать количество сигналов сегодня для пары"""
    today_start = int(time.time()) - 86400  # 24 часа назад
    
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT COUNT(*) FROM signals WHERE pair = ? AND sent_at > ?",
            (pair, today_start)
        ) as cursor:
            row = await cursor.fetchone()
            return row[0] if row else 0

async def log_signal(user_id: int, pair: str, side: str, price: float, confidence: int):
    """Записать отправленный сигнал"""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO signals (user_id, pair, side, price, confidence) VALUES (?, ?, ?, ?, ?)",
            (user_id, pair, side, price, confidence)
        )
        await db.commit()

# ==================== СТАТИСТИКА ====================

async def get_all_user_ids() -> List[int]:
    """Получить все ID пользователей"""
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT user_id FROM users") as cursor:
            rows = await cursor.fetchall()
            return [row[0] for row in rows]

async def get_users_count() -> int:
    """Получить количество пользователей"""
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT COUNT(*) FROM users") as cursor:
            row = await cursor.fetchone()
            return row[0] if row else 0

async def get_subscribed_users_count() -> int:
    """Получить количество пользователей с активной подпиской"""
    current_time = int(time.time())
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT COUNT(*) FROM users WHERE subscription_until > ?",
            (current_time,)
        ) as cursor:
            row = await cursor.fetchone()
            return row[0] if row else 0
