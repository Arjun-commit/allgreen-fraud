"""Locust load test for the scoring API."""

from __future__ import annotations

import random
import uuid

from locust import HttpUser, between, task


class BankIntegrationUser(HttpUser):
    """Simulates one banking session from the bank's perspective."""

    wait_time = between(0.5, 2.0)
    session_id: str = ""
    user_id: str = ""

    def on_start(self) -> None:
        self.session_id = str(uuid.uuid4())
        self.user_id = f"user-{random.randint(1, 10000)}"

    @task(10)
    def send_session_events(self) -> None:
        """High-frequency: browser SDK sends event batches every 5s."""
        events = []
        t = random.randint(0, 300_000)
        for _ in range(random.randint(5, 20)):
            events.append({
                "type": random.choice(["mousemove", "click", "keydown", "scroll"]),
                "ts_ms": t,
                "x": random.randint(0, 1920),
                "y": random.randint(0, 1080),
            })
            t += random.randint(50, 200)
        self.client.post(
            "/v1/events/session",
            json={
                "session_id": self.session_id,
                "user_id": self.user_id,
                "events": events,
            },
        )

    @task(1)
    def score_transaction(self) -> None:
        """Low-frequency: one score per transfer attempt."""
        self.client.post(
            "/v1/score",
            json={
                "session_id": self.session_id,
                "transaction": {
                    "amount": round(random.uniform(10, 10_000), 2),
                    "currency": "USD",
                    "payee_account": f"ACC-{random.randint(100000, 999999)}",
                    "payee_name": "Test Payee",
                    "transfer_type": random.choice(["domestic", "international"]),
                    "is_new_payee": random.random() < 0.3,
                },
            },
        )

    @task(3)
    def poll_friction(self) -> None:
        """Medium-frequency: bank frontend polls for friction updates."""
        self.client.get(f"/v1/friction/{self.session_id}")
