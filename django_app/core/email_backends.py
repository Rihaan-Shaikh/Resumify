import os
import requests
from django.core.mail.backends.base import BaseEmailBackend
from django.core.exceptions import ImproperlyConfigured

class ResendEmailBackend(BaseEmailBackend):
    def __init__(self, fail_silently=False, **kwargs):
        super().__init__(fail_silently=fail_silently, **kwargs)
        self.api_key = os.environ.get('RESEND_API_KEY')
        if not self.api_key and not fail_silently:
            raise ImproperlyConfigured("RESEND_API_KEY environment variable is not set")
        self.api_url = "https://api.resend.com/emails"

    def send_messages(self, email_messages):
        if not email_messages:
            return 0
        
        num_sent = 0
        for message in email_messages:
            try:
                headers = {
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json"
                }
                
                payload = {
                    "from": message.from_email,
                    "to": message.to,
                    "subject": message.subject,
                    "text": message.body,
                }
                
                response = requests.post(self.api_url, json=payload, headers=headers, timeout=10)
                if response.status_code in [200, 201]:
                    num_sent += 1
                else:
                    if not self.fail_silently:
                        response.raise_for_status()
            except Exception:
                if not self.fail_silently:
                    raise
        return num_sent
