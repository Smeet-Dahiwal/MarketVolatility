import json
import sqlite3
from typing import Any, Dict, Optional, List, Tuple

def connect(db_path: str) -> sqlite3.Connection:
    con = sqlite3.connect(db_path)
    con.execute("PRAGMA journal_mode=WAL;")
    con.execute("PRAGMA synchronous=NORMAL;")
    return con

def init_db(con: sqlite3.Connection) -> None:
    con.execute("""
    CREATE TABLE IF NOT EXISTS patterns (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        symbol TEXT NOT NULL,
        tf TEXT NOT NULL,
        ts TEXT NOT NULL,
        trade_type TEXT NOT NULL,
        bias TEXT NOT NULL,
        feature_version INTEGER NOT NULL,
        window INTEGER NOT NULL,
        embedding_json TEXT NOT NULL,
        outcome_json TEXT NOT NULL
    );
    """)
    con.execute("CREATE INDEX IF NOT EXISTS idx_patterns_symbol_tf ON patterns(symbol, tf);")
    con.execute("CREATE INDEX IF NOT EXISTS idx_patterns_ts ON patterns(ts);")
    con.commit()

def insert_pattern(
    con: sqlite3.Connection,
    symbol: str,
    tf: str,
    ts: str,
    trade_type: str,
    bias: str,
    feature_version: int,
    window: int,
    embedding: list,
    outcome: Dict[str, Any],
) -> None:
    con.execute(
        """
        INSERT INTO patterns(symbol, tf, ts, trade_type, bias, feature_version, window, embedding_json, outcome_json)
        VALUES(?,?,?,?,?,?,?,?,?)
        """,
        (
            symbol, tf, ts, trade_type, bias,
            feature_version, window,
            json.dumps(embedding, separators=(",", ":")),
            json.dumps(outcome, separators=(",", ":")),
        )
    )
