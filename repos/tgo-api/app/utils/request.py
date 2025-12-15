"""HTTP request utilities."""

import ipaddress
from typing import Optional
from fastapi import Request


def get_client_language(request: Request, provided_language: Optional[str] = None) -> Optional[str]:
    """
    Get the client's preferred language from the request.
    
    Priority:
    1. If provided_language is given and not empty, use it directly
    2. Accept-Language header (first language in the list)
    
    Args:
        request: FastAPI Request object
        provided_language: Optional language code provided in the request body
        
    Returns:
        The client's preferred language code (e.g., 'en', 'zh-CN'), or None if not available
    """
    # 1. Use provided language if available
    if provided_language and provided_language.strip():
        return provided_language.strip()
    
    # 2. Accept-Language header
    accept_language = request.headers.get("Accept-Language")
    if accept_language:
        # Parse Accept-Language header
        # Format: "en-US,en;q=0.9,zh-CN;q=0.8,zh;q=0.7"
        # Take the first language (highest priority)
        languages = accept_language.split(",")
        if languages:
            # Get first language, strip quality value if present
            first_lang = languages[0].split(";")[0].strip()
            if first_lang:
                return first_lang
    
    return None


def _normalize_ip_candidate(value: str) -> str:
    """
    Normalize a header IP candidate.

    Handles common formats:
    - "1.2.3.4"
    - "1.2.3.4:12345"
    - "[2001:db8::1]:12345"
    - "2001:db8::1"
    """
    v = (value or "").strip().strip('"').strip("'")
    if not v:
        return ""

    # Bracketed IPv6: [addr]:port
    if v.startswith("[") and "]" in v:
        inside = v[1 : v.index("]")]
        return inside.strip()

    # If it looks like IPv4:port, strip the port
    # (For IPv6, there are many ":" so we don't split blindly.)
    if v.count(":") == 1 and "." in v:
        host, _port = v.split(":", 1)
        return host.strip()

    return v


def _is_valid_ip(value: str) -> bool:
    try:
        ipaddress.ip_address(value)
        return True
    except Exception:
        return False


def _is_public_ip(value: str) -> bool:
    """
    Return True when the IP is globally routable (public).
    """
    try:
        ip = ipaddress.ip_address(value)
        return ip.is_global
    except Exception:
        return False


def _pick_best_ip_from_xff(x_forwarded_for: str) -> Optional[str]:
    """
    Pick the best client IP from an X-Forwarded-For chain.

    Strategy:
    - Prefer the first valid public (global) IP in the list.
    - If none are public, fall back to the first valid IP.
    """
    if not x_forwarded_for:
        return None

    parts = [p.strip() for p in x_forwarded_for.split(",") if p.strip()]
    normalized = []
    for p in parts:
        candidate = _normalize_ip_candidate(p)
        if candidate and _is_valid_ip(candidate):
            normalized.append(candidate)

    for ip in normalized:
        if _is_public_ip(ip):
            return ip

    return normalized[0] if normalized else None


def get_client_ip(request: Request, provided_ip: Optional[str] = None) -> Optional[str]:
    """
    Get the real client IP address from the request.
    
    Priority:
    1. If provided_ip is given and not empty, use it directly
    2. X-Forwarded-For header (first IP in the chain, set by proxies like nginx)
    3. X-Real-IP header (set by nginx with real_ip_header directive)
    4. CF-Connecting-IP header (set by Cloudflare)
    5. True-Client-IP header (set by some CDNs)
    6. request.client.host (direct connection, may be proxy IP)
    
    Args:
        request: FastAPI Request object
        provided_ip: Optional IP address provided in the request body
        
    Returns:
        The client's real IP address, or None if not available
    """
    # 1. Use provided IP if available
    if provided_ip and provided_ip.strip():
        ip_value = _normalize_ip_candidate(provided_ip)
        return ip_value if ip_value else provided_ip.strip()
    
    # 2. X-Forwarded-For: client, proxy1, proxy2, ...
    x_forwarded_for = request.headers.get("X-Forwarded-For")
    if x_forwarded_for:
        best = _pick_best_ip_from_xff(x_forwarded_for)
        if best:
            return best
    
    # 3. X-Real-IP (nginx)
    x_real_ip = request.headers.get("X-Real-IP")
    if x_real_ip:
        ip_value = _normalize_ip_candidate(x_real_ip)
        return ip_value if ip_value else x_real_ip.strip()
    
    # 4. CF-Connecting-IP (Cloudflare)
    cf_connecting_ip = request.headers.get("CF-Connecting-IP")
    if cf_connecting_ip:
        ip_value = _normalize_ip_candidate(cf_connecting_ip)
        return ip_value if ip_value else cf_connecting_ip.strip()
    
    # 5. True-Client-IP (some CDNs)
    true_client_ip = request.headers.get("True-Client-IP")
    if true_client_ip:
        ip_value = _normalize_ip_candidate(true_client_ip)
        return ip_value if ip_value else true_client_ip.strip()
    
    # 6. Fall back to request.client.host
    if request.client and request.client.host:
        ip_value = _normalize_ip_candidate(request.client.host)
        return ip_value if ip_value else request.client.host
    
    return None
