"""
Email service module for sending task results and notifications.

This module provides email functionality for the Omni Chat application, allowing
users to receive AI task results via email. It supports multiple email providers
with secure authentication and configurable SMTP settings.

Key Features:
    - SMTP email sending with TLS/SSL support
    - HTML and plain text email composition
    - Configurable email templates for task results
    - Support for major email providers (Gmail, Outlook, Yahoo)
    - Comprehensive error handling and logging
    - Email configuration testing functionality

Supported Providers:
    - Gmail (with App Passwords)
    - Outlook/Hotmail
    - Yahoo Mail
    - Custom SMTP servers

Functions:
    - send_task_email(): Main function to send task result emails
    - format_task_email(): Creates formatted email content
    - test_email_config(): Validates email configuration

Security:
    - Secure SMTP authentication
    - TLS/SSL encryption support
    - Safe credential handling
    - Input validation for email addresses

Usage:
    >>> config = {
    ...     'smtp_server': 'smtp.gmail.com',
    ...     'smtp_port': '587',
    ...     'email_address': 'user@gmail.com',
    ...     'smtp_password': 'app_password',
    ...     'smtp_use_tls': 'true'
    ... }
    >>> send_task_email("recipient@example.com", "Task Result", "Content", config)
"""

import smtplib
import ssl
from datetime import datetime
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Dict, Optional, Any
import logging

logger = logging.getLogger(__name__)


class EmailService:
    """Service for sending emails with task results."""

    def __init__(self, email_config: Dict[str, str]):
        """Initialize email service with configuration.

        Args:
            email_config: Dictionary containing SMTP configuration
        """
        self.smtp_server = email_config.get("smtp_server", "")
        self.smtp_port = int(email_config.get("smtp_port", 587))
        self.email_address = email_config.get("email_address", "")
        self.smtp_password = email_config.get("smtp_password", "")
        self.smtp_use_tls = email_config.get("smtp_use_tls", "true").lower() == "true"

    def is_configured(self) -> bool:
        """Check if email service is properly configured.

        Returns:
            True if all required configuration is present
        """
        required_fields = [
            self.smtp_server,
            self.email_address,
            self.smtp_password,
        ]
        return all(field.strip() for field in required_fields)

    def send_task_result(
        self,
        to_email: str,
        task_name: str,
        task_result: str,
        task_description: str = "",
        execution_time: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Send task result via email.

        Args:
            to_email: Recipient email address
            task_name: Name of the task
            task_result: The result/output from the AI model
            task_description: Optional task description
            execution_time: Optional execution timestamp

        Returns:
            Dictionary with success status and message
        """
        if not self.is_configured():
            return {
                "success": False,
                "error": "Email service is not properly configured. Please check SMTP settings.",
            }

        if not to_email or not to_email.strip():
            return {"success": False, "error": "Recipient email address is required"}

        try:
            # Create timestamp if not provided
            if not execution_time:
                execution_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            # Format timestamp for email subject (mm/dd/yy HH:MM:SS)
            if execution_time:
                try:
                    # Parse the execution time and format for subject
                    dt = datetime.fromisoformat(
                        execution_time.replace("T", " ").replace("Z", "")
                    )
                    subject_timestamp = dt.strftime("%m/%d/%y %H:%M:%S")
                except:
                    # Fallback to current time if parsing fails
                    subject_timestamp = datetime.now().strftime("%m/%d/%y %H:%M:%S")
            else:
                subject_timestamp = datetime.now().strftime("%m/%d/%y %H:%M:%S")

            # Create email message
            message = MIMEMultipart("alternative")
            message["Subject"] = f"{task_name} - {subject_timestamp}"
            message["From"] = self.email_address
            message["To"] = to_email

            # Create email content
            text_content = self._create_text_content(
                task_name, task_result, task_description, execution_time
            )
            html_content = self._create_html_content(
                task_name, task_result, task_description, execution_time
            )

            # Attach parts
            text_part = MIMEText(text_content, "plain")
            html_part = MIMEText(html_content, "html")

            message.attach(text_part)
            message.attach(html_part)

            # Send email
            self._send_email(message, to_email)

            logger.info(f"Task result email sent successfully to {to_email}")
            return {
                "success": True,
                "message": f"Task result sent successfully to {to_email}",
            }

        except Exception as e:
            error_msg = f"Failed to send email: {str(e)}"
            logger.error(error_msg)
            return {"success": False, "error": error_msg}

    def _create_text_content(
        self,
        task_name: str,
        task_result: str,
        task_description: str,
        execution_time: str,
    ) -> str:
        """Create plain text email content."""
        content = f"""
Task Execution Result
==================

Task: {task_name}
Executed: {execution_time}

"""

        if task_description:
            content += f"""Description: {task_description}

"""

        content += f"""Result:
{'-' * 50}
{task_result}
{'-' * 50}

This email was sent automatically by Omni Chat task scheduler.
"""

        return content

    def _create_html_content(
        self,
        task_name: str,
        task_result: str,
        task_description: str,
        execution_time: str,
    ) -> str:
        """Create HTML email content."""
        description_html = ""
        if task_description:
            description_html = f"""
            <p><strong>Description:</strong></p>
            <p style="margin-left: 20px; color: #666;">{self._escape_html(task_description)}</p>
            """

        html_content = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>Task Execution Result</title>
    <style>
        body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; max-width: 800px; margin: 0 auto; padding: 20px; }}
        .header {{ background-color: #f8f9fa; padding: 20px; border-radius: 8px; margin-bottom: 20px; }}
        .task-name {{ color: #2563eb; font-size: 24px; font-weight: bold; margin-bottom: 10px; }}
        .execution-time {{ color: #666; font-size: 14px; }}
        .result-section {{ background-color: #f1f5f9; padding: 20px; border-radius: 8px; border-left: 4px solid #2563eb; }}
        .result-content {{ white-space: pre-wrap; font-family: 'Courier New', monospace; background-color: white; padding: 15px; border-radius: 4px; border: 1px solid #e2e8f0; }}
        .footer {{ margin-top: 30px; padding-top: 20px; border-top: 1px solid #e2e8f0; color: #666; font-size: 12px; }}
    </style>
</head>
<body>
    <div class="header">
        <div class="task-name">{self._escape_html(task_name)}</div>
        <div class="execution-time">Executed: {execution_time}</div>
    </div>
    
    {description_html}
    
    <div class="result-section">
        <h3 style="margin-top: 0; color: #2563eb;">Result:</h3>
        <div class="result-content">{self._escape_html(task_result)}</div>
    </div>
    
    <div class="footer">
        This email was sent automatically by Omni Chat task scheduler.
    </div>
</body>
</html>
"""
        return html_content

    def _escape_html(self, text: str) -> str:
        """Escape HTML special characters."""
        if not text:
            return ""
        return (
            text.replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;")
            .replace("'", "&#x27;")
        )

    def _send_email(self, message: MIMEMultipart, to_email: str) -> None:
        """Send the email message via SMTP."""
        context = ssl.create_default_context()

        with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
            if self.smtp_use_tls:
                server.starttls(context=context)

            if self.email_address and self.smtp_password:
                server.login(self.email_address, self.smtp_password)

            server.sendmail(self.email_address, to_email, message.as_string())


def send_task_email(
    email_config: Dict[str, str],
    to_email: str,
    task_name: str,
    task_result: str,
    task_description: str = "",
    execution_time: Optional[str] = None,
) -> Dict[str, Any]:
    """Convenience function to send task result email.

    Args:
        email_config: SMTP configuration dictionary
        to_email: Recipient email address
        task_name: Name of the task
        task_result: The result/output from the AI model
        task_description: Optional task description
        execution_time: Optional execution timestamp

    Returns:
        Dictionary with success status and message
    """
    email_service = EmailService(email_config)
    return email_service.send_task_result(
        to_email=to_email,
        task_name=task_name,
        task_result=task_result,
        task_description=task_description,
        execution_time=execution_time,
    )
