import uuid
from django.utils import timezone
from datetime import timedelta

def send_verification_email(user):
    token = uuid.uuid4().hex
    profile = user.userprofile
    profile.verification_token = token
    profile.token_expiry = timezone.now() + timedelta(hours=1)
    profile.save()

    link = f"http://13.51.234.234/verify-email/?token={token}"
    user.email_user(
            "Verify Your Email Address",
            f"""Hello {user.username},

        Thank you for using food app! Please verify your email address to activate your account.

        Click the link below to verify your email. This link will expire in 1 hour:

        {link}

        If you did not sign up for an account, you can safely ignore this email.

        Best regards,  
        The MyFoodApp Team
        """
    )