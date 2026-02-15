# market_predictor/db.py
import sqlite3
import time
import json
from typing import Optional, Dict, Any

DB_PATH_DEFAULT = "market_predictor.db"


def now_ts() -> int:
    return int(time.time())


def _connect(db_path: str) -> sqlite3.Connection:
    con = sqlite3.connect(db_path, timeout=30, check_same_thread=False)
    con.row_factory = sqlite3.Row
    return con


def _table_columns(con: sqlite3.Connection, table: str) -> set[str]:
    rows = con.execute(f"PRAGMA table_info({table});").fetchall()
    return {r["name"] for r in rows}


def init_db(db_path: str = DB_PATH_DEFAULT) -> None:
    con = _connect(db_path)
    try:
        con.execute("PRAGMA journal_mode=WAL;")
        con.execute("PRAGMA synchronous=NORMAL;")

        # Key-value state
        con.execute(
            """
            CREATE TABLE IF NOT EXISTS kv_state (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL,
                updated_ts INTEGER NOT NULL
            );
            """
        )

        # Signals
        con.execute(
            """
            CREATE TABLE IF NOT EXISTS signals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ts INTEGER NOT NULL,
                symbol TEXT NOT NULL,
                tf_trend TEXT NOT NULL,
                tf_setup TEXT NOT NULL,
                tf_entry TEXT NOT NULL,
                trade_type TEXT NOT NULL,
                bias TEXT NOT NULL,
                confidence INTEGER NOT NULL,
                expected_direction TEXT,
                expected_min REAL,
                expected_max REAL,
                reasons_json TEXT,
                indicators_json TEXT,
                fingerprint TEXT
            );
            """
        )
        con.execute("CREATE INDEX IF NOT EXISTS idx_signals_symbol_ts ON signals(symbol, ts);")
        con.execute("CREATE INDEX IF NOT EXISTS idx_signals_fp ON signals(fingerprint);")

        # ---- Migration: add patterns_json to signals (if missing) ----
        cols = _table_columns(con, "signals")
        if "patterns_json" not in cols:
            con.execute("ALTER TABLE signals ADD COLUMN patterns_json TEXT;")
            # Optional index for pattern searches later (not necessary now)
            # con.execute("CREATE INDEX IF NOT EXISTS idx_signals_patterns ON signals(symbol, ts);")

        # Trades
        con.execute(
            """
            CREATE TABLE IF NOT EXISTS trades (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ts INTEGER NOT NULL,
                symbol TEXT NOT NULL,
                trade_type TEXT NOT NULL,
                bias TEXT NOT NULL,
                entry REAL,
                stop_loss REAL,
                take_profit REAL,
                rr REAL,
                note TEXT,
                fingerprint TEXT
            );
            """
        )
        con.execute("CREATE INDEX IF NOT EXISTS idx_trades_symbol_ts ON trades(symbol, ts);")
        con.execute("CREATE INDEX IF NOT EXISTS idx_trades_fp ON trades(fingerprint);")

        # Alerts
        con.execute(
            """
            CREATE TABLE IF NOT EXISTS alerts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ts INTEGER NOT NULL,
                symbol TEXT NOT NULL,
                kind TEXT NOT NULL,              -- SETUP / ENTRY / BIAS
                fingerprint TEXT NOT NULL,
                status TEXT NOT NULL,            -- SENT / SKIPPED / FAILED
                error TEXT,
                message_hash TEXT
            );
            """
        )
        con.execute("CREATE INDEX IF NOT EXISTS idx_alerts_symbol_ts ON alerts(symbol, ts);")
        con.execute("CREATE INDEX IF NOT EXISTS idx_alerts_kind_fp ON alerts(kind, fingerprint);")

        # Backtest trades
        con.execute(
            """
            CREATE TABLE IF NOT EXISTS backtest_trades (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ts INTEGER NOT NULL,
                symbol TEXT NOT NULL,
                trade_type TEXT NOT NULL,
                bias TEXT NOT NULL,
                entry REAL NOT NULL,
                stop_loss REAL NOT NULL,
                take_profit REAL NOT NULL,
                rr REAL NOT NULL,
                outcome TEXT NOT NULL,           -- WIN / LOSS / BE
                r_multiple REAL NOT NULL,
                meta_json TEXT
            );
            """
        )
        con.execute("CREATE INDEX IF NOT EXISTS idx_bt_symbol_ts ON backtest_trades(symbol, ts);")
        con.execute("CREATE INDEX IF NOT EXISTS idx_bt_type_bias ON backtest_trades(trade_type, bias);")

        # Phase-2 reserved tables
        con.execute(
            """
            CREATE TABLE IF NOT EXISTS patterns (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ts INTEGER NOT NULL,
                symbol TEXT NOT NULL,
                tf TEXT NOT NULL,
                trade_type TEXT NOT NULL,
                bias TEXT NOT NULL,
                embedding_json TEXT NOT NULL,
                outcome_json TEXT NOT NULL
            );
            """
        )
        con.execute("CREATE INDEX IF NOT EXISTS idx_patterns_key ON patterns(symbol, tf, trade_type, bias);")

        con.execute(
            """
            CREATE TABLE IF NOT EXISTS calibration (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ts INTEGER NOT NULL,
                symbol TEXT NOT NULL,
                trade_type TEXT NOT NULL,
                bias TEXT NOT NULL,
                bucket_json TEXT NOT NULL,
                sample_size INTEGER NOT NULL,
                win_rate REAL NOT NULL,
                avg_r REAL NOT NULL
            );
            """
        )
        con.execute("CREATE INDEX IF NOT EXISTS idx_calib_key ON calibration(symbol, trade_type, bias);")

        con.commit()
    finally:
        con.close()


def kv_get(key: str, db_path: str = DB_PATH_DEFAULT) -> Optional[str]:
    con = _connect(db_path)
    try:
        row = con.execute("SELECT value FROM kv_state WHERE key=?", (key,)).fetchone()
        return row["value"] if row else None
    finally:
        con.close()


def kv_set(key: str, value: str, db_path: str = DB_PATH_DEFAULT) -> None:
    con = _connect(db_path)
    try:
        con.execute(
            """
            INSERT INTO kv_state(key, value, updated_ts)
            VALUES(?, ?, ?)
            ON CONFLICT(key) DO UPDATE SET value=excluded.value, updated_ts=excluded.updated_ts
            """,
            (key, value, now_ts()),
        )
        con.commit()
    finally:
        con.close()


def should_send_alert(
    symbol: str,
    kind: str,
    fingerprint: str,
    cooldown_minutes: int,
    db_path: str = DB_PATH_DEFAULT,
) -> bool:
    con = _connect(db_path)
    try:
        cutoff = now_ts() - int(cooldown_minutes * 60)
        row = con.execute(
            """
            SELECT ts FROM alerts
            WHERE symbol=? AND kind=? AND fingerprint=? AND status='SENT'
              AND ts >= ?
            ORDER BY ts DESC LIMIT 1
            """,
            (symbol, kind, fingerprint, cutoff),
        ).fetchone()
        return row is None
    finally:
        con.close()


def insert_signal(payload: Dict[str, Any], db_path: str = DB_PATH_DEFAULT) -> int:
    """
    payload may optionally include:
      - patterns: dict (stored into patterns_json)
    """
    con = _connect(db_path)
    try:
        cur = con.execute(
            """
            INSERT INTO signals(
                ts, symbol, tf_trend, tf_setup, tf_entry,
                trade_type, bias, confidence,
                expected_direction, expected_min, expected_max,
                reasons_json, indicators_json, fingerprint,
                patterns_json
            )
            VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                payload["ts"],
                payload["symbol"],
                payload.get("tf_trend", "1h"),
                payload.get("tf_setup", "15m"),
                payload.get("tf_entry", "5m"),
                payload["trade_type"],
                payload["bias"],
                int(payload["confidence"]),
                payload.get("expected_direction"),
                payload.get("expected_min"),
                payload.get("expected_max"),
                json.dumps(payload.get("reasons", []), ensure_ascii=False),
                json.dumps(payload.get("indicators", {}), ensure_ascii=False),
                payload.get("fingerprint"),
                json.dumps(payload.get("patterns", {}), ensure_ascii=False),
            ),
        )
        con.commit()
        return int(cur.lastrowid)
    finally:
        con.close()


def insert_trade(payload: Dict[str, Any], db_path: str = DB_PATH_DEFAULT) -> int:
    con = _connect(db_path)
    try:
        cur = con.execute(
            """
            INSERT INTO trades(
                ts, symbol, trade_type, bias,
                entry, stop_loss, take_profit, rr, note, fingerprint
            )
            VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                payload["ts"],
                payload["symbol"],
                payload["trade_type"],
                payload["bias"],
                payload.get("entry"),
                payload.get("stop_loss"),
                payload.get("take_profit"),
                payload.get("rr"),
                payload.get("note"),
                payload.get("fingerprint"),
            ),
        )
        con.commit()
        return int(cur.lastrowid)
    finally:
        con.close()


def insert_alert(payload: Dict[str, Any], db_path: str = DB_PATH_DEFAULT) -> int:
    con = _connect(db_path)
    try:
        cur = con.execute(
            """
            INSERT INTO alerts(
                ts, symbol, kind, fingerprint, status, error, message_hash
            )
            VALUES(?, ?, ?, ?, ?, ?, ?)
            """,
            (
                payload["ts"],
                payload["symbol"],
                payload["kind"],
                payload["fingerprint"],
                payload["status"],
                payload.get("error"),
                payload.get("message_hash"),
            ),
        )
        con.commit()
        return int(cur.lastrowid)
    finally:
        con.close()
