from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from src.robinhood_crypto.signing import RobinhoodCryptoSigner

type QueryValue = str | int | float
type QueryParams = (
    Mapping[str, QueryValue | Sequence[QueryValue]] | Sequence[tuple[str, QueryValue]]
)


class RobinhoodCryptoHTTPError(RuntimeError):
    """Sanitized HTTP failure that retains status and API error details."""

    def __init__(self, *, status_code: int, method: str, path: str, detail: str) -> None:
        super().__init__(f"Robinhood Crypto API {status_code} for {method} {path}: {detail}")
        self.status_code = status_code
        self.method = method
        self.path = path
        self.detail = detail


@dataclass(frozen=True, slots=True)
class RobinhoodCryptoClientConfig:
    base_url: str = "https://trading.robinhood.com"
    timeout_seconds: float = 10.0
    order_submission_enabled: bool = False
    retry_total: int = 3
    retry_backoff_seconds: float = 0.4
    max_pages: int = 100

    def __post_init__(self) -> None:
        if not self.base_url.startswith("https://"):
            raise ValueError("Robinhood Crypto base_url must use HTTPS")
        if self.timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")
        if self.retry_total < 0:
            raise ValueError("retry_total cannot be negative")
        if self.retry_backoff_seconds < 0:
            raise ValueError("retry_backoff_seconds cannot be negative")
        if self.max_pages <= 0:
            raise ValueError("max_pages must be positive")


class RobinhoodCryptoClient:
    """Signed HTTP transport with repeated query params, pagination, and fail-closed writes."""

    def __init__(
        self,
        signer: RobinhoodCryptoSigner,
        *,
        config: RobinhoodCryptoClientConfig | None = None,
        session: requests.Session | None = None,
    ) -> None:
        self._signer = signer
        self._config = config or RobinhoodCryptoClientConfig()
        self._session = session or self._build_session(self._config)

    def get(self, path: str, *, params: QueryParams | None = None) -> dict[str, Any]:
        return self.request("GET", path, params=params)

    def get_pages(self, path: str, *, params: QueryParams | None = None) -> list[dict[str, Any]]:
        pages: list[dict[str, Any]] = []
        next_path: str | None = path
        next_params = params
        seen: set[str] = set()

        while next_path is not None:
            if len(pages) >= self._config.max_pages:
                raise RuntimeError("Robinhood Crypto pagination exceeded configured max_pages")
            page = self.get(next_path, params=next_params)
            pages.append(page)
            next_url = page.get("next")
            if not next_url:
                break
            if not isinstance(next_url, str):
                raise RuntimeError("Robinhood Crypto pagination 'next' must be a URL string")
            next_path, next_params = self._split_next_url(next_url)
            marker = self._signed_path(next_path, next_params)
            if marker in seen:
                raise RuntimeError("Robinhood Crypto pagination loop detected")
            seen.add(marker)
        return pages

    def request(
        self,
        method: str,
        path: str,
        *,
        params: QueryParams | None = None,
        payload: Mapping[str, Any] | None = None,
        mutating: bool = False,
    ) -> dict[str, Any]:
        normalized_method = method.strip().upper()
        if mutating and not self._config.order_submission_enabled:
            raise RuntimeError("Robinhood Crypto mutating requests are disabled")
        if payload is not None and normalized_method in {"GET", "HEAD"}:
            raise ValueError(f"{normalized_method} requests cannot include a JSON payload")
        if not path.startswith("/"):
            raise ValueError("request path must start with '/'")

        normalized_params = self._normalize_params(params)
        signed_path = self._signed_path(path, normalized_params)
        body = json.dumps(payload, separators=(",", ":")) if payload is not None else ""
        signed_headers = self._signer.sign(method=normalized_method, path=signed_path, body=body)
        headers = {**signed_headers.as_dict(), "Accept": "application/json"}
        if payload is not None:
            headers["Content-Type"] = "application/json"

        response = self._session.request(
            normalized_method,
            f"{self._config.base_url.rstrip('/')}{path}",
            params=normalized_params or None,
            data=body or None,
            headers=headers,
            timeout=self._config.timeout_seconds,
        )
        if not response.ok:
            raise self._http_error(response, method=normalized_method, path=signed_path)
        try:
            data = response.json()
        except ValueError as exc:
            raise RuntimeError("Robinhood Crypto response was not valid JSON") from exc
        if not isinstance(data, dict):
            raise RuntimeError("Robinhood Crypto response must be a JSON object")
        return data

    @staticmethod
    def _normalize_params(params: QueryParams | None) -> list[tuple[str, QueryValue]]:
        if params is None:
            return []
        if isinstance(params, Mapping):
            normalized: list[tuple[str, QueryValue]] = []
            for key, value in params.items():
                if isinstance(value, Sequence) and not isinstance(value, str):
                    normalized.extend((str(key), item) for item in value)
                else:
                    normalized.append((str(key), value))
            return normalized
        return [(str(key), value) for key, value in params]

    @staticmethod
    def _signed_path(path: str, params: QueryParams | None) -> str:
        query = urlencode(RobinhoodCryptoClient._normalize_params(params), doseq=True)
        return f"{path}?{query}" if query else path

    def _split_next_url(self, next_url: str) -> tuple[str, list[tuple[str, str]]]:
        parsed = urlsplit(next_url)
        if parsed.scheme or parsed.netloc:
            expected = urlsplit(self._config.base_url)
            if parsed.scheme != expected.scheme or parsed.netloc != expected.netloc:
                raise RuntimeError("Robinhood Crypto pagination URL changed API host")
        if not parsed.path.startswith("/"):
            raise RuntimeError("Robinhood Crypto pagination URL has an invalid path")
        return parsed.path, parse_qsl(parsed.query, keep_blank_values=True)

    @staticmethod
    def _http_error(
        response: requests.Response, *, method: str, path: str
    ) -> RobinhoodCryptoHTTPError:
        detail = response.reason or "request failed"
        try:
            payload = response.json()
            if isinstance(payload, dict):
                candidate = payload.get("detail") or payload.get("message") or payload.get("error")
                if candidate:
                    detail = str(candidate)
        except ValueError:
            text = response.text.strip()
            if text:
                detail = text[:500]
        return RobinhoodCryptoHTTPError(
            status_code=response.status_code,
            method=method,
            path=path,
            detail=detail,
        )

    @staticmethod
    def _build_session(config: RobinhoodCryptoClientConfig) -> requests.Session:
        retry = Retry(
            total=config.retry_total,
            connect=config.retry_total,
            read=config.retry_total,
            status=config.retry_total,
            backoff_factor=config.retry_backoff_seconds,
            status_forcelist=(429, 500, 502, 503, 504),
            allowed_methods=frozenset({"GET", "HEAD", "OPTIONS"}),
            respect_retry_after_header=True,
            raise_on_status=False,
        )
        adapter = HTTPAdapter(max_retries=retry)
        session = requests.Session()
        session.mount("https://", adapter)
        return session
