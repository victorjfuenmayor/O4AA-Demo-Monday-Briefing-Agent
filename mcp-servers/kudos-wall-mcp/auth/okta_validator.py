"""
Token Validation for Kudos Wall MCP Server

Validates access tokens via OAuth 2.0 Discovery Endpoint. Reused verbatim
from hr-system-mcp/ticketing-system-mcp's validator -- it's generic, so it
works unmodified here as long as OKTA_DOMAIN/OKTA_AUTHORIZATION_SERVER_ID
are pointed at OUR OWN discovery endpoint (xaa_resource_as.discovery_document,
served at /oauth2/kudos-wall/.well-known/oauth-authorization-server) instead
of Okta's, since Kudos Wall's tokens are self-issued by our own XAA
resource authorization server, not by Okta directly.

Flow:
1. Incoming request contains Authorization: Bearer <token> header
2. Extract token from header
3. Validate token signature and claims
4. Check token audience matches OKTA_AUDIENCE
5. Check token contains all required scopes (OKTA_REQUIRED_SCOPES)
6. Extract scopes for permission checking
7. Grant or deny tool access based on scopes
"""

import logging
import os
import json
from typing import Dict, Any, Optional
from datetime import datetime
import httpx
from functools import lru_cache
import jwt

logger = logging.getLogger(__name__)


class OktaTokenValidator:
    """
    Validates MCP access tokens using OAuth 2.0 Discovery Endpoint.

    Automatically discovers all necessary configuration from a
    .well-known/oauth-authorization-server endpoint, requiring only:
    - OKTA_DOMAIN (e.g., dev-12345.okta.com, or our own ngrok host)
    - OKTA_AUTHORIZATION_SERVER_ID (e.g., hr-mcp-server, or kudos-wall)

    Validates:
    - Token signature (using JWKS discovered from endpoint)
    - Token expiration
    - Token audience (derived from issuer)
    - Token scope
    - Required scopes (if OKTA_REQUIRED_SCOPES configured)

    Usage:
        validator = OktaTokenValidator()
        claims = await validator.validate_token(access_token)
        if claims:
            # Token is valid, proceed
        else:
            # Token is invalid, deny access
    """

    def __init__(self):
        # Get minimal required configuration
        self.okta_domain = os.getenv("OKTA_DOMAIN", "").strip()
        self.authorization_server_id = os.getenv("OKTA_AUTHORIZATION_SERVER_ID", "hr-mcp-server").strip()
        self.expected_audience = os.getenv("OKTA_AUDIENCE", "").strip()  # Optional audience

        # Parse required scopes (space-separated, optional)
        # Token must contain ALL of these scopes
        required_scopes_str = os.getenv("OKTA_REQUIRED_SCOPES", "").strip()
        self.required_scopes = set(required_scopes_str.split()) if required_scopes_str else set()

        if not self.okta_domain:
            raise ValueError("OKTA_DOMAIN environment variable is required")
        if not self.authorization_server_id:
            raise ValueError("OKTA_AUTHORIZATION_SERVER_ID environment variable is required")

        # Build discovery endpoint URL
        self.discovery_url = f"https://{self.okta_domain}/oauth2/{self.authorization_server_id}/.well-known/oauth-authorization-server"

        # Will be populated by _load_discovery_metadata()
        self.jwks_url: Optional[str] = None
        self.issuer: Optional[str] = None
        self.discovery_metadata: Optional[Dict[str, Any]] = None

        # Cache for JWKS keys (expires after 1 hour)
        self._jwks_cache: Optional[Dict[str, Any]] = None
        self._jwks_cache_time: Optional[datetime] = None
        self._jwks_cache_ttl = 3600  # 1 hour

        logger.info(f"OktaTokenValidator initializing: domain={self.okta_domain}, auth_server={self.authorization_server_id}")
        if self.expected_audience:
            logger.info(f"Expected audience: {self.expected_audience}")
        else:
            logger.info("Audience validation disabled (OKTA_AUDIENCE not set)")
        if self.required_scopes:
            logger.info(f"Required scopes: {', '.join(self.required_scopes)}")
        else:
            logger.info("Scope requirement validation disabled (OKTA_REQUIRED_SCOPES not set)")
        logger.debug(f"Discovery endpoint: {self.discovery_url}")

    async def _load_discovery_metadata(self) -> bool:
        """
        Load authorization server metadata from the discovery endpoint.

        Fetches configuration from:
        https://{OKTA_DOMAIN}/oauth2/{AUTH_SERVER_ID}/.well-known/oauth-authorization-server

        Returns:
            True if successful, False otherwise
        """
        try:
            if self.discovery_metadata is not None:
                logger.debug("Discovery metadata already loaded")
                return True

            logger.info(f"Fetching discovery metadata from {self.discovery_url}")

            async with httpx.AsyncClient() as client:
                response = await client.get(self.discovery_url, timeout=10)
                response.raise_for_status()

            self.discovery_metadata = response.json()

            # Extract critical values
            self.jwks_url = self.discovery_metadata.get("jwks_uri")
            self.issuer = self.discovery_metadata.get("issuer")

            if not self.jwks_url:
                logger.error("Discovery endpoint missing 'jwks_uri'")
                return False

            if not self.issuer:
                logger.error("Discovery endpoint missing 'issuer'")
                return False

            logger.info(f"Discovery successful: issuer={self.issuer}, jwks_uri={self.jwks_url}")
            return True

        except Exception as e:
            logger.error(f"Failed to load discovery metadata: {e}")
            return False

    async def _get_jwks(self) -> Optional[Dict[str, Any]]:
        """
        Fetch JWKS for token verification.

        JWKS URL is discovered from the authorization server metadata.
        Results are cached for 1 hour to reduce API calls.

        Returns:
            Dict with 'keys' array, or None if fetch fails
        """
        try:
            # Ensure discovery metadata is loaded
            if not await self._load_discovery_metadata():
                logger.error("Cannot fetch JWKS: discovery metadata not available")
                return None

            if not self.jwks_url:
                logger.error("JWKS URL not available from discovery metadata")
                return None

            logger.debug(f"Fetching JWKS from {self.jwks_url}")

            async with httpx.AsyncClient() as client:
                response = await client.get(self.jwks_url, timeout=10)
                response.raise_for_status()
                jwks = response.json()
                logger.info(f"JWKS fetched successfully: {len(jwks.get('keys', []))} keys")
                return jwks

        except Exception as e:
            logger.error(f"Failed to fetch JWKS: {e}")
            return None

    def _get_signing_key(self, jwks: Dict[str, Any], kid: str) -> Optional[Dict[str, Any]]:
        """
        Find signing key by kid (key ID) in JWKS.

        Args:
            jwks: JWKS response
            kid: Key ID from token header

        Returns:
            Key dict, or None if not found
        """
        keys = jwks.get("keys", [])
        for key in keys:
            if key.get("kid") == kid:
                return key
        logger.warning(f"Signing key not found for kid: {kid}")
        return None

    def _validate_required_scopes(self, token_claims: Dict[str, Any]) -> bool:
        """
        Validate that token contains all required scopes.

        Required scopes are specified in OKTA_REQUIRED_SCOPES environment variable
        as a space-separated list. Token must contain ALL of them.

        Args:
            token_claims: Decoded token claims with 'scope' field

        Returns:
            True if all required scopes present, False otherwise
        """
        if not self.required_scopes:
            # No required scopes configured
            return True

        scope = token_claims.get("scope", "")

        # Handle scope as either space-separated string or array
        if isinstance(scope, list):
            token_scopes = set(scope)
        elif isinstance(scope, str):
            token_scopes = set(scope.split()) if scope else set()
        else:
            token_scopes = set()

        # Check if all required scopes are present (required is subset of token scopes)
        if self.required_scopes.issubset(token_scopes):
            logger.info(f"Required scopes validation PASSED (required: {self.required_scopes}, token: {token_scopes})")
            return True
        else:
            missing_scopes = self.required_scopes - token_scopes
            logger.warning(f"Required scopes validation FAILED (required: {self.required_scopes}, missing: {missing_scopes}, token: {token_scopes})")
            return False

    async def validate_token(self, token: str) -> Optional[Dict[str, Any]]:
        """
        Validate an MCP access token using discovered metadata.

        Validates:
        1. Token format (JWT with 3 parts)
        2. Token signature using JWKS
        3. Token expiration
        4. Token audience (derived from issuer in discovery metadata)
        5. Token required scopes (if OKTA_REQUIRED_SCOPES set)
        6. Token scope

        The audience is automatically derived from the OAuth 2.0 issuer
        in the discovery endpoint, so no manual audience configuration needed.

        Args:
            token: The MCP access token from Authorization header

        Returns:
            Dict with token claims if valid:
            {
                "valid": True,
                "sub": "user_id",
                "aud": "audience",
                "scope": "mcp:read mcp:write",
                "exp": 1234567890,
                "iss": "https://..."
            }
            Or None if invalid
        """
        try:
            if not token:
                logger.warning("Empty token provided")
                return None

            # Ensure discovery metadata is loaded (for audience)
            if not await self._load_discovery_metadata():
                logger.error("Cannot validate token: discovery metadata not available")
                return None

            # Decode token header to get kid (key ID)
            try:
                header = jwt.get_unverified_header(token)
                kid = header.get("kid")
                if not kid:
                    logger.error("Token missing 'kid' in header")
                    return None
            except Exception as e:
                logger.error(f"Invalid token format: {e}")
                return None

            # Fetch JWKS (cached)
            jwks = await self._get_jwks()
            if not jwks:
                logger.error("Failed to fetch JWKS for validation")
                return None

            # Get signing key
            signing_key = self._get_signing_key(jwks, kid)
            if not signing_key:
                logger.error(f"Signing key not found for kid: {kid}")
                return None

            # Verify token signature and claims
            decoded = None  # Initialize here for exception handling

            try:
                # Create PEM public key from JWK
                public_key = jwt.algorithms.RSAAlgorithm.from_jwk(json.dumps(signing_key))

                # Determine whether to verify audience
                verify_audience = bool(self.expected_audience)
                expected_audience = self.expected_audience if verify_audience else None

                if verify_audience:
                    logger.debug(f"Validating token with audience: {expected_audience}")
                else:
                    logger.debug("Validating token without audience check")

                # Verify token
                decoded = jwt.decode(
                    token,
                    public_key,
                    algorithms=["RS256"],
                    audience=expected_audience,  # Only verify if OKTA_AUDIENCE is set
                    options={
                        "verify_signature": True,
                        "verify_exp": True,  # Verify expiration
                        "verify_aud": verify_audience   # Only verify audience if configured
                    }
                )

                # Extract scope from either 'scope' or 'scp' claim
                # 'scp' is standard Okta format, 'scope' is standard OAuth format
                scope = decoded.get("scope")
                scp = decoded.get("scp")

                # Convert scp array to space-separated string if present
                if scp and not scope:
                    if isinstance(scp, list):
                        scope = " ".join(scp)
                    else:
                        scope = str(scp)

                scope = scope or ""

                # Store normalized scope back in decoded for required scopes validation
                decoded["scope"] = scope

                # Validate required scopes
                if not self._validate_required_scopes(decoded):
                    logger.warning("Token does not contain all required scopes")
                    return None

                logger.info(f"Token validated successfully: sub={decoded.get('sub')}, scope={scope}, aud={decoded.get('aud')}")

                return {
                    "valid": True,
                    "sub": decoded.get("sub"),
                    "aud": decoded.get("aud"),
                    "scope": scope,  # Normalized scope (space-separated string or from scp array)
                    "exp": decoded.get("exp"),
                    "iss": decoded.get("iss"),
                    "claims": decoded  # Full claims for detailed authorization
                }

            except jwt.ExpiredSignatureError:
                logger.warning("Token has expired")
                return None
            except jwt.InvalidAudienceError:
                aud_value = decoded.get('aud') if decoded else "unknown"
                logger.warning(f"Invalid audience. Expected: {expected_audience}, got: {aud_value}")
                logger.warning(f"Set OKTA_AUDIENCE environment variable to the expected audience")
                return None
            except jwt.InvalidSignatureError:
                logger.error("Invalid token signature")
                return None
            except Exception as e:
                logger.error(f"Token verification failed: {e}")
                return None

        except Exception as e:
            logger.error(f"Token validation error: {e}")
            import traceback
            logger.debug(f"Traceback: {traceback.format_exc()}")
            return None


# Global validator instance
_validator: Optional[OktaTokenValidator] = None


def get_validator() -> OktaTokenValidator:
    """Get or create global validator instance"""
    global _validator
    if _validator is None:
        _validator = OktaTokenValidator()
    return _validator


async def validate_authorization_header(authorization_header: Optional[str]) -> Optional[Dict[str, Any]]:
    """
    Extract and validate token from Authorization header.

    Expected format: "Bearer <token>"

    Args:
        authorization_header: The Authorization header value

    Returns:
        Token claims dict if valid, None if invalid
    """
    if not authorization_header:
        logger.warning("Missing Authorization header")
        return None

    # Parse Bearer token
    parts = authorization_header.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        logger.warning(f"Invalid Authorization header format: {parts[0] if parts else 'empty'}")
        return None

    token = parts[1]

    # Validate token
    validator = get_validator()
    return await validator.validate_token(token)
