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
            print(f"  ❌ IMAP connection failed: {e}")
            return False
    
    def disconnect(self):
        """Disconnect from IMAP server."""
        if self.connection:
            try:
                self.connection.logout()
            except:
                pass
            self.connection = None
    
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
    
    def wait_for_verification_email(
        self, 
        sender_contains: str = "france-visas",
        subject_contains: str = "",
        max_wait_seconds: int = 300,
        poll_interval: int = 10
    ) -> Tuple[bool, Optional[str]]:
        """
        Wait for verification email and extract the link.
        
        Args:
            sender_contains: String to match in sender address
            subject_contains: String to match in subject (optional)
            max_wait_seconds: Maximum time to wait
            poll_interval: Seconds between inbox checks
            
        Returns:
            Tuple of (success, verification_link)
        """
        if not self.connection:
            if not self.connect():
                return False, None
        
        print(f"\n📧 Waiting for verification email...")
        print(f"   Looking for sender containing: '{sender_contains}'")
        
        start_time = time.time()
        checked_ids = set()
        
        while time.time() - start_time < max_wait_seconds:
            elapsed = int(time.time() - start_time)
            remaining = max_wait_seconds - elapsed
            print(f"   ⏳ Checking inbox... ({remaining}s remaining)")
            
            try:
                # Select inbox
                self.connection.select("INBOX")
                
                # Search for recent emails
                status, messages = self.connection.search(None, "ALL")
                
                if status != "OK":
                    time.sleep(poll_interval)
                    continue
                
                email_ids = messages[0].split()
                
                # Check most recent emails first (reverse order)
                for email_id in reversed(email_ids[-20:]):  # Last 20 emails
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
                    
                    # Get sender
                    sender = msg.get("From", "").lower()
                    
                    # Get subject
                    subject_raw = msg.get("Subject", "")
                    subject = ""
                    if subject_raw:
                        decoded = decode_header(subject_raw)
                        for part, encoding in decoded:
                            if isinstance(part, bytes):
                                subject += part.decode(encoding or 'utf-8', errors='ignore')
                            else:
                                subject += part
                    
                    # Check if this is the verification email
                    if sender_contains.lower() not in sender:
                        continue
                    
                    if subject_contains and subject_contains.lower() not in subject.lower():
                        continue
                    
                    print(f"\n   ✓ Found email from: {sender}")
                    print(f"   ✓ Subject: {subject[:50]}...")
                    
                    # Extract body and find link
                    body = self.get_email_body(msg)
                    link = self.find_verification_link(body)
                    
                    if link:
                        print(f"   ✓ Verification link found!")
                        return True, link
                    else:
                        print(f"   ⚠️ Email found but no verification link detected")
                
            except Exception as e:
                print(f"   ⚠️ Error checking inbox: {e}")
            
            time.sleep(poll_interval)
        
        print(f"   ❌ Timeout: No verification email found in {max_wait_seconds}s")
        return False, None


def test_email_reader():
    """Test the email reader."""
    config = EmailConfig(
        email_address="test@example.com",
        email_password="password",
        imap_server="imap.example.com"
    )
    
    reader = EmailReader(config)
    if reader.connect():
        success, link = reader.wait_for_verification_email(
            sender_contains="france-visas",
            max_wait_seconds=60
        )
        print(f"Result: {success}, Link: {link}")
        reader.disconnect()


if __name__ == "__main__":
    test_email_reader()

