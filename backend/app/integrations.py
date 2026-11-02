"""Bounded HTTP requests. Never forward provider errors or credentials to clients."""
import httpx
from fastapi import HTTPException


def request(method, url, service, **kwargs):
    try:
        with httpx.Client(timeout=15, follow_redirects=False) as client:
            response = client.request(method, url, **kwargs)
    except httpx.RequestError:
        raise HTTPException(503, f"{service} temporarily unavailable") from None
    if response.status_code == 429:
        raise HTTPException(429, f"{service} rate limit reached")
    if response.status_code == 404:
        raise HTTPException(404, f"{service} item not found")
    if not response.is_success:
        raise HTTPException(503, f"{service} temporarily unavailable; check service configuration")
    return response


def json_request(method, url, service, **kwargs):
    response = request(method, url, service, **kwargs)
    try:
        data = response.json()
        if not isinstance(data, dict):
            raise ValueError()
        return data
    except ValueError:
        raise HTTPException(502, f"Invalid response from {service}") from None
