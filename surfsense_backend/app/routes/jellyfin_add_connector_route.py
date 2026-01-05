"""
Routes for adding and testing Jellyfin connector.
"""

import logging

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.connectors.jellyfin_connector import JellyfinConnector
from app.db import User, get_async_session
from app.users import current_active_user
from app.utils.url_validator import validate_connector_url

logger = logging.getLogger(__name__)

router = APIRouter()


class JellyfinConnectorRequest(BaseModel):
    """Request model for Jellyfin connector."""

    server_url: str
    api_key: str
    user_id: str | None = None  # Optional Jellyfin user ID for user-specific data


class JellyfinTestResponse(BaseModel):
    """Response model for Jellyfin connection test."""

    success: bool
    message: str
    server_name: str | None = None
    version: str | None = None
    users: list[dict] | None = None


@router.post("/auth/jellyfin/test", response_model=JellyfinTestResponse)
async def test_jellyfin_connection(
    request: JellyfinConnectorRequest,
    user: User = Depends(current_active_user),
    session: AsyncSession = Depends(get_async_session),
):
    """
    Test connection to a Jellyfin server.

    Args:
        request: Jellyfin connection details
        user: Current authenticated user
        session: Database session

    Returns:
        Connection test result with server info
    """
    try:
        # Normalize URL
        server_url = request.server_url.strip()
        if not server_url.startswith(("http://", "https://")):
            server_url = f"http://{server_url}"

        # Validate URL to prevent SSRF attacks and get validated IPs for TOCTOU protection
        server_url, validated_ips = await validate_connector_url(server_url, connector_type="Jellyfin")

        # Initialize connector using validated IPs to prevent DNS rebinding
        jellyfin_client = JellyfinConnector(
            server_url=server_url,
            api_key=request.api_key,
            user_id=request.user_id,
            validated_ips=validated_ips,
        )

        # Test connection
        success, error = await jellyfin_client.test_connection()

        if not success:
            return JellyfinTestResponse(
                success=False,
                message=f"Connection failed: {error}",
            )

        # Get server info for response using validated IPs to prevent DNS rebinding
        info, info_error = await jellyfin_client.get_server_info()
        if info:
            server_name = info.get("ServerName", "Unknown")
            version = info.get("Version", "Unknown")
        else:
            # If fetching server info fails, continue without it; connection was already tested above.
            server_name = None
            version = None

        # Get users if no user_id specified (helps user select one)
        users = None
        if not request.user_id:
            users_list, _ = await jellyfin_client.get_users()
            if users_list:
                users = [
                    {"id": u.get("Id"), "name": u.get("Name")} for u in users_list
                ]

        return JellyfinTestResponse(
            success=True,
            message="Connection successful",
            server_name=server_name,
            version=version,
            users=users,
        )

    except Exception as e:
        logger.error(f"Error testing Jellyfin connection: {e!s}", exc_info=True)
        raise HTTPException(
            status_code=500, detail="Error testing connection. Please check your server URL and API key."
        ) from e


@router.post("/auth/jellyfin/add")
async def add_jellyfin_connector(
    request: JellyfinConnectorRequest,
    user: User = Depends(current_active_user),
    session: AsyncSession = Depends(get_async_session),
):
    """
    Add a Jellyfin connector configuration.

    This endpoint validates the connection and returns the config
    to be used when creating a SearchSourceConnector.

    Args:
        request: Jellyfin connection details
        user: Current authenticated user
        session: Database session

    Returns:
        Connector configuration dict
    """
    try:
        # Normalize URL
        server_url = request.server_url.strip()
        if not server_url.startswith(("http://", "https://")):
            server_url = f"http://{server_url}"

        # Validate URL to prevent SSRF attacks and get validated IPs for TOCTOU protection
        server_url, validated_ips = await validate_connector_url(server_url, connector_type="Jellyfin")

        # Initialize connector using validated IPs to prevent DNS rebinding
        jellyfin_client = JellyfinConnector(
            server_url=server_url,
            api_key=request.api_key,
            user_id=request.user_id,
            validated_ips=validated_ips,
        )

        # Test connection
        success, error = await jellyfin_client.test_connection()

        if not success:
            raise HTTPException(
                status_code=400, detail=f"Connection failed: {error}"
            )

        # Return config for creating the connector
        config = {
            "SERVER_URL": server_url,
            "API_KEY": request.api_key,
        }

        if request.user_id:
            config["USER_ID"] = request.user_id

        return {
            "success": True,
            "message": "Jellyfin connection validated",
            "config": config,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error adding Jellyfin connector: {e!s}", exc_info=True)
        raise HTTPException(
            status_code=500, detail="Error adding connector. Please check your configuration and try again."
        ) from e
