"""Google Drive API service for file upload via OAuth 2.0."""

import asyncio
import io
import logging

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload

from app.config import settings

logger = logging.getLogger(__name__)

SCOPES = ["https://www.googleapis.com/auth/drive.file"]
TOKEN_URI = "https://oauth2.googleapis.com/token"


class GoogleDriveService:
    """Upload files to Google Drive using OAuth 2.0 user credentials."""

    def __init__(self) -> None:
        refresh_token = settings.google_drive_refresh_token
        if not refresh_token:
            raise ValueError(
                "Google Drive is not authenticated. "
                "Please authenticate via Settings → Google Drive Export."
            )

        credentials = Credentials(
            token=None,
            refresh_token=refresh_token,
            token_uri=TOKEN_URI,
            client_id=settings.google_drive_client_id,
            client_secret=settings.google_drive_client_secret,
            scopes=SCOPES,
        )
        self._service = build("drive", "v3", credentials=credentials)

    async def upload_text_file(
        self, filename: str, content: str, folder_id: str | None = None
    ) -> tuple[str, str]:
        """Upload text content as a file to Google Drive.

        Returns:
            Tuple of (file_id, web_view_link).
        """
        target_folder = folder_id or settings.google_drive_folder_id

        file_metadata: dict = {"name": filename, "mimeType": "text/plain"}
        if target_folder:
            file_metadata["parents"] = [target_folder]

        media = MediaIoBaseUpload(
            io.BytesIO(content.encode("utf-8")),
            mimetype="text/plain",
            resumable=False,
        )

        def _upload() -> tuple[str, str]:
            file = (
                self._service.files()
                .create(
                    body=file_metadata,
                    media_body=media,
                    fields="id,webViewLink",
                )
                .execute()
            )
            return file["id"], file["webViewLink"]

        return await asyncio.to_thread(_upload)

    async def update_text_file(self, file_id: str, content: str) -> tuple[str, str]:
        """Update an existing file's content.

        Returns:
            Tuple of (file_id, web_view_link).
        """
        media = MediaIoBaseUpload(
            io.BytesIO(content.encode("utf-8")),
            mimetype="text/plain",
            resumable=False,
        )

        def _update() -> tuple[str, str]:
            file = (
                self._service.files()
                .update(
                    fileId=file_id,
                    media_body=media,
                    fields="id,webViewLink",
                )
                .execute()
            )
            return file["id"], file["webViewLink"]

        return await asyncio.to_thread(_update)
