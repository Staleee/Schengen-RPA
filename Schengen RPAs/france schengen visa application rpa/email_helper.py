"""
Email Helper Module
===================
Reads verification emails via IMAP and extracts verification links.
"""

import imaplib
import email
import re
import time
from email.header import decode_header
from email.utils import parseaddr
from typing import Optional, Tuple
from dataclasses import dataclass


@dataclass
class EmailConfig:
    """Email configuration for IMAP access."""
    email_address: str
    email_password: str
    imap_server: str
    imap_port: int = 993
    use_ssl: bool = True


class EmailReader:
    """Reads emails via IMAP to find verification links."""
    
    def __init__(self, config: EmailConfig):
        self.config = config
        self.connection: Optional[imaplib.IMAP4_SSL] = None
    
    def connect(self) -> bool:
        """Connect to the IMAP server."""
        try:
            if self.config.use_ssl:
                self.connection = imaplib.IMAP4_SSL(
                    self.config.imap_server, 
                    self.config.imap_port
                )
            else:
                self.connection = imaplib.IMAP4(
                    self.config.imap_server, 
                    self.config.imap_port
                )
            
            self.connection.login(
                self.config.email_address, 
                self.config.email_password
            )
            print(f"  ✓ Connected to {self.config.imap_server}")
            return True
            
        except Exception as e:
            err_msg = str(e).strip()
            print(f"  ❌ IMAP connection failed: {err_msg}")
            print(f"     Server: {self.config.imap_server}:{self.config.imap_port} (SSL={self.config.use_ssl})")
            if "getaddrinfo failed" in err_msg or "11001" in err_msg or "Name or service not known" in err_msg:
                print("     → Hostname could not be resolved. Check imap_server (e.g. Gmail: imap.gmail.com, Outlook: outlook.office365.com).")
            elif "Authentication failed" in err_msg or "LOGIN failed" in err_msg:
                print("     → Login failed. For Gmail use an App Password, not your normal password.")
            return False
    
    def disconnect(self):
        """Disconnect from IMAP server."""
        if self.connection:
            try:
                self.connection.logout()
            except:
                pass
            self.connection = None
    
    def _decode_header_value(self, raw: str) -> str:
        """Decode MIME-encoded header (e.g. From, Subject) to plain string."""
        if not raw:
            return ""
        decoded = decode_header(raw)
        out = ""
        for part, encoding in decoded:
            if isinstance(part, bytes):
                out += part.decode(encoding or "utf-8", errors="ignore")
            else:
                out += str(part)
        return out.strip()

    def _get_sender_normalized(self, msg) -> str:
        """Get sender string for matching: decoded From header + parsed email address."""
        raw_from = msg.get("From", "") or ""
        decoded = self._decode_header_value(raw_from).lower()
        # Also get the actual email address (e.g. "noreply@interieur.gouv.fr" from "France Visas <noreply@interieur.gouv.fr>")
        _, addr = parseaddr(raw_from)
        if addr:
            decoded += " " + addr.lower()
        return decoded

    def get_email_body(self, msg) -> str:
        """Extract body text from email message."""
        body = ""
        
        if msg.is_multipart():
            for part in msg.walk():
                content_type = part.get_content_type()
                content_disposition = str(part.get("Content-Disposition"))
                
                if content_type == "text/plain" and "attachment" not in content_disposition:
                    try:
                        body += part.get_payload(decode=True).decode('utf-8', errors='ignore')
                    except:
                        pass
                elif content_type == "text/html" and "attachment" not in content_disposition:
                    try:
                        body += part.get_payload(decode=True).decode('utf-8', errors='ignore')
                    except:
                        pass
        else:
            try:
                body = msg.get_payload(decode=True).decode('utf-8', errors='ignore')
            except:
                pass
        
        return body
    
    def find_verification_link(self, body: str) -> Optional[str]:
        """Extract France-Visas verification link from email body."""
        
        # Patterns for verification links
        patterns = [
            r'https?://[^\s<>"\']+france-visas[^\s<>"\']*verify[^\s<>"\']*',
            r'https?://[^\s<>"\']+france-visas[^\s<>"\']*confirm[^\s<>"\']*',
            r'https?://[^\s<>"\']+france-visas[^\s<>"\']*activation[^\s<>"\']*',
            r'https?://connect\.france-visas\.gouv\.fr[^\s<>"\']+',
            r'https?://[^\s<>"\']*france-visas\.gouv\.fr[^\s<>"\']*action[^\s<>"\']*',
            # Generic activation/verification links
            r'https?://[^\s<>"\']+/login-actions/[^\s<>"\']+',
        ]
        
        for pattern in patterns:
            matches = re.findall(pattern, body, re.IGNORECASE)
            if matches:
                # Clean the URL
                link = matches[0].rstrip('.,;:)')
                # Remove any trailing HTML
                link = re.sub(r'<.*', '', link)
                return link
        
        # Fallback: find any link with common verification keywords
        all_links = re.findall(r'https?://[^\s<>"\']+', body)
        keywords = ['verify', 'confirm', 'activate', 'validation', 'action']
        
        for link in all_links:
            link_lower = link.lower()
            if any(kw in link_lower for kw in keywords):
                return link.rstrip('.,;:)')
        
        return None

    def find_verification_code(self, body: str) -> Optional[str]:
        """Extract verification code (e.g. 6 digits) from email body."""
        # Strip HTML tags for text search
        text = re.sub(r'<[^>]+>', ' ', body)
        text = re.sub(r'\s+', ' ', text)
        # 6-digit code (common for email verification)
        six_digit = re.findall(r'\b(\d{6})\b', text)
        if six_digit:
            return six_digit[0]
        # 4–8 digit codes
        for length in (8, 7, 5, 4):
            m = re.findall(rf'\b(\d{{{length}}})\b', text)
            if m:
                return m[0]
        # "code: 123456" or "votre code : 123456" or "verification code is 123456"
        for pattern in [
            r'code\s*[:\s]+\s*(\d{4,8})',
            r'verification\s*code\s*[:\s]+\s*(\d{4,8})',
            r'votre\s*code\s*[:\s]+\s*(\d{4,8})',
            r'(\d{6})',  # any 6-digit number
        ]:
            m = re.search(pattern, text, re.IGNORECASE)
            if m:
                return m.group(1).strip()
        return None
    
    # France-Visas sends verification from this address
    FRANCE_VISAS_SENDER = "noreply@interieur.gouv.fr"

    def wait_for_verification_email(
        self, 
        sender_contains: str = "interieur.gouv.fr",
        subject_contains: str = "",
        max_wait_seconds: int = 300,
        poll_interval: int = 10
    ) -> Tuple[bool, Optional[str], Optional[str]]:
        """
        Wait for verification email and extract link and/or code.
        Looks for the most recent email from the given sender (e.g. noreply@interieur.gouv.fr).
        
        Returns:
            Tuple of (success, verification_link, verification_code)
        """
        if not self.connection:
            if not self.connect():
                return False, None, None
        
        print(f"\n📧 Waiting for verification email...")
        print(f"   Looking for most recent email from sender containing: '{sender_contains}'")
        
        start_time = time.time()
        checked_ids = set()
        
        while time.time() - start_time < max_wait_seconds:
            elapsed = int(time.time() - start_time)
            remaining = max_wait_seconds - elapsed
            print(f"   ⏳ Checking inbox... ({remaining}s remaining)")
            
            try:
                # Select inbox
                self.connection.select("INBOX")
                
                # Search: try FROM noreply@interieur.gouv.fr first (some servers want with/without quotes)
                from_addr = self.FRANCE_VISAS_SENDER if "interieur.gouv.fr" in sender_contains.lower() else None
                status, messages = ("OK", [b""])
                if from_addr:
                    for query in (f'FROM "{from_addr}"', f"FROM {from_addr}"):
                        try:
                            status, messages = self.connection.search(None, query)
                            if status == "OK" and messages[0].strip():
                                break
                        except Exception:
                            pass
                if status != "OK" or not messages[0].strip():
                    status, messages = self.connection.search(None, "ALL")
                
                if status != "OK":
                    time.sleep(poll_interval)
                    continue
                
                email_ids = messages[0].split()
                # Most recent first (IMAP IDs often ascending by time; reverse to get newest first)
                email_ids = list(reversed(email_ids))
                n = len(email_ids)
                if elapsed == 0 or n > 0:
                    print(f"   Checking {min(n, 30)} emails (newest first)...")
                
                # Check most recent emails first (already newest first)
                for email_id in email_ids[:30]:  # Last 30 emails
                    if email_id in checked_ids:
                        continue
                    
                    checked_ids.add(email_id)
                    
                    # Fetch email
                    status, msg_data = self.connection.fetch(email_id, "(RFC822)")
                    
                    if status != "OK":
                        continue
                    
                    # Parse email
                    raw_email = msg_data[0][1]
                    msg = email.message_from_bytes(raw_email)
                    
                    # Get sender (decoded From + parsed address so we always match noreply@interieur.gouv.fr)
                    sender = self._get_sender_normalized(msg)
                    
                    # Get subject (decoded)
                    subject_raw = msg.get("Subject", "")
                    subject = self._decode_header_value(subject_raw) if subject_raw else ""
                    
                    # Check if this is the verification email (match interieur.gouv.fr or noreply@interieur.gouv.fr)
                    want = sender_contains.lower()
                    if want not in sender and "noreply@interieur.gouv.fr" not in sender:
                        continue
                    
                    if subject_contains and subject_contains.lower() not in subject.lower():
                        continue
                    
                    print(f"\n   ✓ Found email from: {sender[:80]}")
                    print(f"   ✓ Subject: {subject[:50]}...")
                    
                    # Extract body and find link and/or code
                    body = self.get_email_body(msg)
                    link = self.find_verification_link(body)
                    code = self.find_verification_code(body)
                    if link:
                        print(f"   ✓ Verification link found!")
                    if code:
                        print(f"   ✓ Verification code found: {code}")
                    if link or code:
                        return True, link, code
                    else:
                        print(f"   ⚠️ Email found but no verification link or code detected")
                
            except Exception as e:
                print(f"   ⚠️ Error checking inbox: {e}")
            
            time.sleep(poll_interval)
        
        print(f"   ❌ Timeout: No verification email found in {max_wait_seconds}s")
        print(f"     (Looking for sender: {self.FRANCE_VISAS_SENDER}. Try increasing email_wait_seconds if the email is slow.)")
        return False, None, None


def test_email_reader():
    """Test the email reader."""
    config = EmailConfig(
        email_address="test@example.com",
        email_password="password",
        imap_server="imap.example.com"
    )
    
    reader = EmailReader(config)
    if reader.connect():
        success, link, code = reader.wait_for_verification_email(
            sender_contains="interieur.gouv.fr",
            max_wait_seconds=60
        )
        print(f"Result: {success}, Link: {link}, Code: {code}")
        reader.disconnect()


if __name__ == "__main__":
    test_email_reader()

