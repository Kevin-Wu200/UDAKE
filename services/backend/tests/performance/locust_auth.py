"""Locust scenarios for auth module load and stress testing."""

from __future__ import annotations

import os
from typing import Optional

from locust import HttpUser, between, task

TEST_EMAIL = os.getenv("AUTH_TEST_EMAIL", "load-user@example.com")
TEST_PASSWORD = os.getenv("AUTH_TEST_PASSWORD", "StrongPass123")
TEST_PRODUCT_KEY = os.getenv("AUTH_TEST_PRODUCT_KEY", "ABC-1234-5678-9XYZ")


class AuthUser(HttpUser):
    """Simulates auth-heavy client behavior."""

    wait_time = between(0.5, 2.0)

    def on_start(self) -> None:
        self.refresh_token: Optional[str] = None
        self._login()

    def _login(self) -> None:
        with self.client.post(
            "/api/auth/login",
            name="auth_login",
            json={
                "email": TEST_EMAIL,
                "password": TEST_PASSWORD,
                "device_info": {
                    "device_id": f"locust-{self.environment.runner.user_count}",
                    "platform": "web",
                },
            },
            catch_response=True,
        ) as response:
            if response.status_code != 200:
                response.failure(f"login failed: {response.status_code}")
                return
            payload = response.json().get("data", {})
            self.refresh_token = payload.get("refresh_token")
            if not self.refresh_token:
                response.failure("missing refresh token")

    @task(6)
    def login_flow(self) -> None:
        self._login()

    @task(2)
    def refresh_flow(self) -> None:
        if not self.refresh_token:
            self._login()
            return
        with self.client.post(
            "/api/auth/refresh",
            name="auth_refresh",
            json={"refresh_token": self.refresh_token},
            catch_response=True,
        ) as response:
            if response.status_code != 200:
                response.failure(f"refresh failed: {response.status_code}")

    @task(1)
    def csrf_token(self) -> None:
        with self.client.get("/api/auth/csrf-token", name="auth_csrf_token", catch_response=True) as response:
            if response.status_code != 200:
                response.failure(f"csrf token failed: {response.status_code}")

    @task(1)
    def health_check(self) -> None:
        with self.client.get("/health", name="health_check", catch_response=True) as response:
            if response.status_code != 200:
                response.failure(f"health failed: {response.status_code}")


class RegistrationUser(HttpUser):
    """Optional register/load scenario for burst testing."""

    wait_time = between(1.0, 3.0)
    weight = 1

    @task(1)
    def register_flow(self) -> None:
        suffix = os.urandom(4).hex()
        email = f"locust-{suffix}@example.com"
        with self.client.post(
            "/api/auth/register",
            name="auth_register",
            json={
                "email": email,
                "password": TEST_PASSWORD,
                "product_key": TEST_PRODUCT_KEY,
            },
            catch_response=True,
        ) as response:
            if response.status_code not in (200, 400, 429):
                response.failure(f"register unexpected status: {response.status_code}")
