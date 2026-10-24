"""Notification layer: AWS SES email and AWS SNS SMS."""
import os
import boto3
from botocore.exceptions import ClientError

SES_REGION = os.environ.get("SES_REGION", "us-east-1")
SES_FROM = os.environ.get("SES_FROM", "gillisw@cua.edu")
SES_ENABLED = os.environ.get("SES_ENABLED", "1") != "0"

ses_client = boto3.client("ses", region_name=SES_REGION) if SES_ENABLED else None

SNS_REGION = os.environ.get("SNS_REGION", "us-east-1")
SNS_ENABLED = os.environ.get("SNS_ENABLED", "1") != "0"
sns_client = boto3.client("sns", region_name=SNS_REGION) if SNS_ENABLED else None


def send_swap_notification(assigned_name, assigned_email, note_body, manager_name):
    """Send an email notification via SES when a swap is approved.

    Returns True on success, False on failure or if email is missing.
    """
    if not ses_client or not assigned_email:
        return False
    subject = f"Shift Coverage Assignment - {assigned_name}"
    body = (
        f"Hi {assigned_name},\n\n"
        f"{manager_name} has assigned you to cover a shift.\n\n"
        f"Details:\n"
        f"  Note: {note_body}\n\n"
        f"Please confirm you can cover this shift.\n\n"
        f"- AI Shift Manager\n"
        f"CUA Busch School AI Vibe Coding Contest, Fall 2026"
    )
    try:
        ses_client.send_email(
            Source=SES_FROM,
            Destination={"ToAddresses": [assigned_email]},
            Message={
                "Subject": {"Data": subject},
                "Body": {"Text": {"Data": body}},
            },
        )
        return True
    except ClientError:
        return False


def send_swap_sms(assigned_name, assigned_phone, note_body):
    """Send an SMS notification via SNS when a swap is approved.

    Returns True on success, False on failure or if phone is missing.
    """
    if not sns_client or not assigned_phone:
        return False
    message = (
        f"Hi {assigned_name}, you have been assigned to cover a shift. "
        f"Details: {note_body[:100]}. - AI Shift Manager"
    )
    try:
        sns_client.publish(PhoneNumber=assigned_phone, Message=message)
        return True
    except ClientError:
        return False
