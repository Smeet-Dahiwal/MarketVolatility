# market_predictor/pattern_runtime.py
import os
import json
import sqlite3
from typing import Dict, Any, Optional, List, Tuple
import numpy as np

from market_predictor.pattern_embedding import make_embedding

def _cosine_sim(a: np.ndarray, b: np.ndarray) -> float:
    denom = (np.linalg.norm(a) * np.linalg.norm(b)) + 1e-12
    return float(np.dot(a, b) / denom)

def load_rows(db_path: str, symbol: str, tf: str, trade_type: str, bias: str) -> List[Tuple]:
    con = sqlite3.connect(db_path)
    try:
        cur = con.execute(
            """
            SELECT embedding_json, outcome_json
            FROM patterns
            WHERE symbol=? AND tf=? AND trade_type=? AND bias=?
            """,
            (symbol, tf, trade_type, bias),
        )
        return cur.fetchall()
    finally:
        con.close()

def pattern_stats(
    df_15m,
    symbol: str,
    tf: str,
    trade_type: str,
    bias: str,
    db_path: str = "patterns.db",
    top_k: int = 30,
    min_rows: int = 30,
    embed_window: int = 32,
) -> Dict[str, Any]:
    """
    Returns stats based on nearest historical embeddings stored in SQLite.
    outcome_json expected to contain: win(bool), future_return(float), r_multiple(optional)
    """
    if not os.path.exists(db_path):
        return {"available": False, "reason": f"DB not found: {db_path}"}

    try:
        rows = load_rows(db_path, symbol, tf, trade_type, bias)
    except Exception as e:
        return {"available": False, "reason": f"DB read error: {e}"}

    if len(rows) < min_rows:
        return {"available": True, "count_total": len(rows), "count_used": 0, "reason": "Not enough patterns"}

    try:
        cur_emb = make_embedding(df_15m, window=embed_window)
    except Exception as e:
        return {"available": True, "count_total": len(rows), "count_used": 0, "reason": f"Embedding error: {e}"}

    scored = []
    for emb_json, out_json in rows:
        try:
            emb = np.array(json.loads(emb_json), dtype=np.float32)
            sim = _cosine_sim(cur_emb, emb)
            out = json.loads(out_json)
            scored.append((sim, out))
        except Exception:
            continue

    if not scored:
        return {"available": True, "count_total": len(rows), "count_used": 0, "reason": "No valid rows"}

    scored.sort(key=lambda x: x[0], reverse=True)
    top = scored[:top_k]

    sims = [s for s, _ in top]
    wins = [1 if o.get("win") else 0 for _, o in top]
    fut = [float(o.get("future_return", 0.0)) for _, o in top]

    return {
        "available": True,
        "count_total": len(rows),
        "count_used": len(top),
        "avg_similarity": float(np.mean(sims)),
        "best_similarity": float(np.max(sims)),
        "win_rate": float(np.mean(wins)),
        "avg_future_return": float(np.mean(fut)),
    }
