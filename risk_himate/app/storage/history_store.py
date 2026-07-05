"""History store interfaces and persistence backends."""

from __future__ import annotations

from pathlib import Path
import json
import sqlite3

from risk_himate.app.core.schemas import RiskReport


class HistoryStore:
    def get_latest_report(self, company: str) -> RiskReport | None:
        raise NotImplementedError

    def save_report(self, report: RiskReport) -> None:
        raise NotImplementedError


class NullHistoryStore(HistoryStore):
    def get_latest_report(self, company: str) -> RiskReport | None:
        return None

    def save_report(self, report: RiskReport) -> None:
        return None


class JsonHistoryStore(HistoryStore):
    def __init__(self, path: str) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.path.exists():
            self.path.write_text("[]", encoding="utf-8")

    def get_latest_report(self, company: str) -> RiskReport | None:
        records = self._load_records()
        matching = [item for item in records if item.get("company") == company]
        if not matching:
            return None
        latest = sorted(matching, key=lambda item: item.get("timestamp", ""), reverse=True)[0]
        return RiskReport(**latest)

    def save_report(self, report: RiskReport) -> None:
        records = self._load_records()
        records.append(report.model_dump())
        self.path.write_text(
            json.dumps(records, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def _load_records(self) -> list[dict]:
        return json.loads(self.path.read_text(encoding="utf-8"))


class SQLiteHistoryStore(HistoryStore):
    def __init__(self, path: str) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.path)

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS reports (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    company TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    overall_score REAL NOT NULL,
                    payload TEXT NOT NULL
                )
                """
            )
            connection.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_reports_company_timestamp
                ON reports(company, timestamp DESC)
                """
            )

    def get_latest_report(self, company: str) -> RiskReport | None:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT payload
                FROM reports
                WHERE company = ?
                ORDER BY timestamp DESC, id DESC
                LIMIT 1
                """,
                (company,),
            ).fetchone()
        if row is None:
            return None
        return RiskReport(**json.loads(row[0]))

    def save_report(self, report: RiskReport) -> None:
        payload = json.dumps(report.model_dump(), ensure_ascii=False)
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO reports(company, timestamp, overall_score, payload)
                VALUES (?, ?, ?, ?)
                """,
                (report.company, report.timestamp, report.overall_score, payload),
            )


def build_history_store(kind: str, path: str | None) -> HistoryStore:
    if kind == "none":
        return NullHistoryStore()
    if path is None:
        raise ValueError(f"History store '{kind}' requires a path.")
    if kind == "json":
        return JsonHistoryStore(path)
    if kind == "sqlite":
        return SQLiteHistoryStore(path)
    raise ValueError(f"Unsupported history store kind: {kind}")


def compute_trend(current_score: float, previous_report: RiskReport | None) -> tuple[str | None, float | None]:
    if previous_report is None:
        return None, None
    delta = round(current_score - previous_report.overall_score, 2)
    if delta >= 8:
        return "up", delta
    if delta <= -8:
        return "down", delta
    return "stable", delta
