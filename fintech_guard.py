import sqlite3
from datetime import datetime

class FintechGuard:
    def __init__(self):
        # подключаемся к базе данных
        self.conn = sqlite3.connect("bank.db")
        self.cursor = self.conn.cursor()
        self.cursor.execute("PRAGMA foreign_keys = ON")

        # создаем таблицы
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT,
                balance INTEGER,
                status TEXT
            )
        """)
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS transactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                sender_id INTEGER,
                receiver_id INTEGER,
                amount INTEGER,
                timestamp TEXT,
                status TEXT,
                FOREIGN KEY (sender_id) REFERENCES users (id),
                FOREIGN KEY (receiver_id) REFERENCES users (id)
            )
        """)
        self.conn.commit()

    def _is_active(self, user_id):
        self.cursor.execute("SELECT status FROM users WHERE id = ?", (user_id,))
        row = self.cursor.fetchone()
        if row is None:
            return False
        else:
            return row[0] == "active"

    def _has_enough_funds(self, user_id, amount):
        self.cursor.execute("SELECT balance FROM users WHERE id = ?", (user_id,))
        row = self.cursor.fetchone()
        if row is None:
            return False
        else:
            balance = row[0]
            return balance >= amount

    def _check_frequency(self, user_id):
        self.cursor.execute("""
            SELECT COUNT(*) FROM transactions
            WHERE sender_id = ?
            AND status = 'success'
            AND timestamp > datetime('now', '-30 seconds')
        """, (user_id,))
        row = self.cursor.fetchone()
        count = row[0]
        if count >= 3:
            # блокировка пользователя
            self.cursor.execute("UPDATE users SET status = 'blocked' WHERE id = ?", (user_id,))
            self.conn.commit()
            return False
        else:
            return True

    def transfer_money(self, sender_id, receiver_id, amount):
        now = datetime.now()
        timestamp_now = now.strftime("%Y-%m-%d %H:%M:%S")

        is_sender_active = self._is_active(sender_id)
        if not is_sender_active:
            self.cursor.execute("""
                INSERT INTO transactions (sender_id, receiver_id, amount, timestamp, status)
                VALUES (?, ?, ?, ?, ?)
            """, (sender_id, receiver_id, amount, timestamp_now, 'rejected'))
            self.conn.commit()
            return "Пользователь заблокирован или не существует"

        is_receiver_active = self._is_active(receiver_id)
        if not is_receiver_active:
            self.cursor.execute("""
                INSERT INTO transactions (sender_id, receiver_id, amount, timestamp, status)
                VALUES (?, ?, ?, ?, ?)
            """, (sender_id, receiver_id, amount, timestamp_now, 'rejected'))
            self.conn.commit()
            return "Пользователь заблокирован или не существует"

        is_enough = self._has_enough_funds(sender_id, amount)
        if not is_enough:
            self.cursor.execute("""
                INSERT INTO transactions (sender_id, receiver_id, amount, timestamp, status)
                VALUES (?, ?, ?, ?, ?)
            """, (sender_id, receiver_id, amount, timestamp_now, 'rejected'))
            self.conn.commit()
            return "Недостаточно средств"

        is_frequency = self._check_frequency(sender_id)
        if not is_frequency:
            self.cursor.execute("""
                INSERT INTO transactions (sender_id, receiver_id, amount, timestamp, status)
                VALUES (?, ?, ?, ?, ?)
            """, (sender_id, receiver_id, amount, timestamp_now, 'rejected'))
            self.conn.commit()
            return "Транзакция заблокирована: подозрительная активность"

        # Все проверки пройдены - совершаем перевод
        self.cursor.execute("UPDATE users SET balance = balance - ? WHERE id = ?", (amount, sender_id))
        self.cursor.execute("UPDATE users SET balance = balance + ? WHERE id = ?", (amount, receiver_id))

        self.cursor.execute("""
            INSERT INTO transactions (sender_id, receiver_id, amount, timestamp, status)
            VALUES (?, ?, ?, ?, ?)
        """, (sender_id, receiver_id, amount, timestamp_now, 'success'))

        self.conn.commit()
        return "Перевод выполнен успешно"
