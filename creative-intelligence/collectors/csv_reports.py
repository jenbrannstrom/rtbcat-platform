"""Gmail CSV report fetcher for advertising data.

This module fetches and parses CSV reports from Gmail attachments,
commonly used for advertising platform reports.
"""

import asyncio
import base64
import csv
import io
import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

logger = logging.getLogger(__name__)


@dataclass
class ReportAttachment:
    """Represents a CSV report attachment from Gmail."""

    message_id: str
    attachment_id: str
    filename: str
    subject: str
    sender: str
    received_date: datetime
    data: bytes


@dataclass
class ParsedReport:
    """Represents a parsed CSV report with metadata."""

    source: ReportAttachment
    headers: list[str]
    rows: list[dict[str, str]]
    row_count: int


class GmailCSVFetcher:
    """Fetches CSV report attachments from Gmail.

    This client searches Gmail for messages with CSV attachments
    matching specified criteria and parses them for analysis.

    Attributes:
        user_id: Gmail user ID (default: 'me' for authenticated user).
    """

    SCOPES = [
        "https://www.googleapis.com/auth/gmail.readonly",
    ]

    def __init__(
        self,
        credentials: Credentials,
        user_id: str = "me",
    ) -> None:
        """Initialize the Gmail CSV fetcher.

        Args:
            credentials: Google OAuth2 credentials with Gmail scope.
            user_id: Gmail user ID (default: 'me').
        """
        self.user_id = user_id
        self._credentials = credentials
        self._service = None

    def _get_service(self):
        """Lazy initialization of the Gmail service."""
        if self._service is None:
            self._service = build("gmail", "v1", credentials=self._credentials)
        return self._service

    async def search_messages(
        self,
        query: str,
        max_results: int = 100,
    ) -> list[str]:
        """Search Gmail for messages matching a query.

        Args:
            query: Gmail search query (e.g., 'from:reports@example.com has:attachment').
            max_results: Maximum number of message IDs to return.

        Returns:
            List of message IDs matching the query.
        """
        service = self._get_service()
        loop = asyncio.get_event_loop()

        message_ids = []
        page_token = None

        while len(message_ids) < max_results:
            result = await loop.run_in_executor(
                None,
                lambda: service.users()
                .messages()
                .list(
                    userId=self.user_id,
                    q=query,
                    maxResults=min(100, max_results - len(message_ids)),
                    pageToken=page_token,
                )
                .execute(),
            )

            messages = result.get("messages", [])
            message_ids.extend([m["id"] for m in messages])

            page_token = result.get("nextPageToken")
            if not page_token:
                break

        return message_ids[:max_results]

    async def get_csv_attachments(
        self,
        message_id: str,
    ) -> list[ReportAttachment]:
        """Get all CSV attachments from a Gmail message.

        Args:
            message_id: The Gmail message ID.

        Returns:
            List of ReportAttachment objects for CSV files found.
        """
        service = self._get_service()
        loop = asyncio.get_event_loop()

        # Get message metadata
        message = await loop.run_in_executor(
            None,
            lambda: service.users()
            .messages()
            .get(userId=self.user_id, id=message_id, format="full")
            .execute(),
        )

        headers = message.get("payload", {}).get("headers", [])
        subject = next(
            (h["value"] for h in headers if h["name"].lower() == "subject"),
            "No Subject",
        )
        sender = next(
            (h["value"] for h in headers if h["name"].lower() == "from"),
            "Unknown",
        )

        # Parse internal date
        internal_date = int(message.get("internalDate", 0))
        received_date = datetime.fromtimestamp(internal_date / 1000)

        attachments = []

        # Find CSV attachments in message parts
        parts = message.get("payload", {}).get("parts", [])
        for part in parts:
            filename = part.get("filename", "")
            if not filename.lower().endswith(".csv"):
                continue

            attachment_id = part.get("body", {}).get("attachmentId")
            if not attachment_id:
                continue

            # Fetch the attachment data
            attachment = await loop.run_in_executor(
                None,
                lambda aid=attachment_id: service.users()
                .messages()
                .attachments()
                .get(userId=self.user_id, messageId=message_id, id=aid)
                .execute(),
            )

            data = base64.urlsafe_b64decode(attachment["data"])

            attachments.append(
                ReportAttachment(
                    message_id=message_id,
                    attachment_id=attachment_id,
                    filename=filename,
                    subject=subject,
                    sender=sender,
                    received_date=received_date,
                    data=data,
                )
            )

        return attachments

    @staticmethod
    def parse_csv(
        attachment: ReportAttachment,
        encoding: str = "utf-8",
        delimiter: str = ",",
    ) -> ParsedReport:
        """Parse a CSV attachment into structured data.

        Args:
            attachment: The ReportAttachment to parse.
            encoding: Character encoding of the CSV file.
            delimiter: CSV delimiter character.

        Returns:
            ParsedReport with headers and row data.
        """
        content = attachment.data.decode(encoding)
        reader = csv.DictReader(io.StringIO(content), delimiter=delimiter)

        rows = list(reader)

        return ParsedReport(
            source=attachment,
            headers=reader.fieldnames or [],
            rows=rows,
            row_count=len(rows),
        )

    async def fetch_reports(
        self,
        query: str,
        max_messages: int = 10,
        parse: bool = True,
    ) -> list[ParsedReport | ReportAttachment]:
        """Fetch and optionally parse CSV reports from Gmail.

        Args:
            query: Gmail search query for finding report emails.
            max_messages: Maximum number of messages to process.
            parse: Whether to parse CSVs or return raw attachments.

        Returns:
            List of ParsedReport (if parse=True) or ReportAttachment objects.
        """
        message_ids = await self.search_messages(query, max_messages)
        logger.info(f"Found {len(message_ids)} messages matching query")

        results = []

        for message_id in message_ids:
            try:
                attachments = await self.get_csv_attachments(message_id)

                for attachment in attachments:
                    if parse:
                        try:
                            parsed = self.parse_csv(attachment)
                            results.append(parsed)
                            logger.info(
                                f"Parsed {parsed.row_count} rows from "
                                f"{attachment.filename}"
                            )
                        except Exception as e:
                            logger.warning(
                                f"Failed to parse {attachment.filename}: {e}"
                            )
                            results.append(attachment)
                    else:
                        results.append(attachment)

            except Exception as e:
                logger.error(f"Failed to process message {message_id}: {e}")

        return results

    async def fetch_latest_report(
        self,
        sender_filter: Optional[str] = None,
        subject_filter: Optional[str] = None,
    ) -> Optional[ParsedReport]:
        """Fetch the most recent CSV report matching filters.

        Args:
            sender_filter: Filter by sender email address.
            subject_filter: Filter by subject line content.

        Returns:
            The most recent ParsedReport or None if not found.
        """
        query_parts = ["has:attachment", "filename:csv"]

        if sender_filter:
            query_parts.append(f"from:{sender_filter}")
        if subject_filter:
            query_parts.append(f"subject:{subject_filter}")

        query = " ".join(query_parts)

        reports = await self.fetch_reports(query, max_messages=1, parse=True)

        if reports and isinstance(reports[0], ParsedReport):
            return reports[0]

        return None
