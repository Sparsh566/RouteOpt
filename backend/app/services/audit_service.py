"""
Audit and Route History Persistence Service
Provides SQLite-backed persistence for commercial fleet optimization runs and compliance audits.
"""

import json
import logging
import os
import sqlite3
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger("routeopt.audit")

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "route_history.db")


class AuditService:
    @classmethod
    def _get_connection(cls) -> sqlite3.Connection:
        conn = sqlite3.connect(DB_PATH, timeout=5.0)
        conn.row_factory = sqlite3.Row
        return conn

    @classmethod
    def init_db(cls) -> None:
        try:
            with cls._get_connection() as conn:
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS route_optimization_history (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        created_at TEXT NOT NULL,
                        region TEXT NOT NULL,
                        status TEXT NOT NULL,
                        solver_used TEXT NOT NULL,
                        stops_count INTEGER NOT NULL,
                        fleet_count INTEGER NOT NULL,
                        total_distance_km REAL NOT NULL,
                        total_duration_hours REAL NOT NULL,
                        total_cost_inr REAL NOT NULL,
                        solve_duration_ms REAL NOT NULL,
                        dropped_stops_count INTEGER NOT NULL,
                        compliance_notes_json TEXT,
                        validation_errors_count INTEGER NOT NULL
                    )
                """)
                conn.commit()
        except Exception as e:
            logger.error(f"Failed to initialize route_history.db: {e}")

    @classmethod
    def record_run(
        cls,
        region: str,
        status: str,
        solver_used: str,
        stops_count: int,
        fleet_count: int,
        total_distance_km: float,
        total_duration_hours: float,
        total_cost_inr: float,
        solve_duration_ms: float,
        dropped_stops_count: int,
        compliance_notes: list[str],
        validation_errors_count: int,
    ) -> int | None:
        cls.init_db()
        try:
            now_iso = datetime.now(timezone.utc).isoformat()
            with cls._get_connection() as conn:
                cur = conn.cursor()
                cur.execute(
                    """
                    INSERT INTO route_optimization_history (
                        created_at, region, status, solver_used, stops_count, fleet_count,
                        total_distance_km, total_duration_hours, total_cost_inr,
                        solve_duration_ms, dropped_stops_count, compliance_notes_json,
                        validation_errors_count
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        now_iso,
                        region,
                        status,
                        solver_used,
                        stops_count,
                        fleet_count,
                        total_distance_km,
                        total_duration_hours,
                        total_cost_inr,
                        solve_duration_ms,
                        dropped_stops_count,
                        json.dumps(compliance_notes),
                        validation_errors_count,
                    ),
                )
                conn.commit()
                return cur.lastrowid
        except Exception as e:
            logger.warning(f"Could not record optimization audit log: {e}")
            return None

    @classmethod
    def get_recent_runs(cls, limit: int = 20) -> list[dict[str, Any]]:
        cls.init_db()
        try:
            with cls._get_connection() as conn:
                cur = conn.cursor()
                cur.execute(
                    """
                    SELECT id, created_at, region, status, solver_used, stops_count, fleet_count,
                           total_distance_km, total_duration_hours, total_cost_inr,
                           solve_duration_ms, dropped_stops_count, compliance_notes_json,
                           validation_errors_count
                    FROM route_optimization_history
                    ORDER BY id DESC
                    LIMIT ?
                    """,
                    (limit,),
                )
                rows = cur.fetchall()
                results = []
                for r in rows:
                    row_dict = dict(r)
                    try:
                        row_dict["compliance_notes"] = json.loads(row_dict.pop("compliance_notes_json", "[]"))
                    except Exception:
                        row_dict["compliance_notes"] = []
                    results.append(row_dict)
                return results
        except Exception as e:
            logger.warning(f"Could not read optimization history: {e}")
            return []
