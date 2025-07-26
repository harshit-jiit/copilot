from django.template.loader import render_to_string
import requests
import uuid
import re
from django.utils.text import slugify
import uuid
from gymowners.models import Domain
from datetime import datetime
import random
import string
from rest_framework.permissions import BasePermission
from accounts.models import LoginSession
from django.utils import timezone
import socket
from django.conf import settings


def schema_mode(mode):  # mode = 'public' or 'tenant'
    def decorator(view_func):
        view_func.schema_mode = mode
        return view_func
    return decorator


def is_local_dev():
    host = socket.gethostname()
    return host in ["localhost", "127.0.0.1"] or host.startswith("DESKTOP")


def generate_random_password(length=10):
    chars = string.ascii_letters + string.digits + "!@#$%^&*()"
    return ''.join(random.choice(chars) for _ in range(length))


def send_password_email_html(email, password, package_name, package_duration, gym_name, gym_location):
    MAILGUN_DOMAIN = 'YOUR_MAILGUN_DOMAIN'
    MAILGUN_API_KEY = 'YOUR_MAILGUN_API_KEY'
    FROM_EMAIL = f"Gym Admin <postmaster@{MAILGUN_DOMAIN}>"

    html_content = render_to_string('emails/membership_welcome.html', {
        'email': email,
        'password': password,
        'package_name': package_name,
        'package_duration': package_duration,
        'gym_name': gym_name,
        'gym_location': gym_location
    })

    # Send email via Mailgun HTTP API
    response = requests.post(
        f"https://api.mailgun.net/v3/{MAILGUN_DOMAIN}/messages",
        auth=("api", MAILGUN_API_KEY),
        data={
            "from": FROM_EMAIL,
            "to": [email],
            "subject": f"Welcome to {gym_name} - Your Membership Details",
            "html": html_content  # send HTML content here
        }
    )
    return response

def to_aware_datetime(date_obj):
    # If you have a date, convert it to datetime at midnight first:
    dt = datetime.combine(date_obj, datetime.min.time())
    # Then make it timezone-aware using Django's current timezone
    return timezone.make_aware(dt)



def generate_subdomain_from_name(name: str) -> str:
    # Lowercase, remove special characters, replace spaces with hyphens
    name = name.lower()
    name = re.sub(r'[^a-z0-9\s-]', '', name)
    name = re.sub(r'\s+', '-', name)
    return name.strip('-')

# def generate_unique_subdomain(name: str) -> str:
#     # Step 1: Slugify name
#     name = name.lower()
#     name = re.sub(r'[^a-z0-9\s-]', '', name)  # remove special chars
#     name = re.sub(r'\s+', '-', name).strip('-')  # spaces to hyphens

#     # Step 2: Add short UUID (6 chars)
#     unique_id = str(uuid.uuid4())[:6]

#     return f"{name}-{unique_id}"


def generate_unique_subdomain(name):
    base = slugify(name) or 'gym'
    slug = base
    while Domain.objects.filter(domain=slug,is_primary=True).exists():
        suffix = uuid.uuid4().hex[:4]
        slug = f"{base}-{suffix}"
    return slug

def get_token_via_header(request):
    # get the header jwt token and the refresh token from the request headers
    auth_header = request.headers.get('Authorization', '')
    if auth_header.startswith('Bearer '):
        jwt_token = auth_header.split(' ')[1].strip()
    else:
        jwt_token = None

    return jwt_token

def get_token_via_cookies(request):
    # get the jwt token and the refresh token from the request cookies
    jwt_token = request.COOKIES.get('jwt_token')

    return jwt_token


def set_cookies(response, jwt_token, refresh_token, domain=None):
    # set the jwt token and the refresh token in the response cookies
    set_jwt_cookie(response, jwt_token, domain)
    response.set_cookie(domain = domain,
                        key='refresh_token',
                        value=refresh_token,
                        httponly=True,
                        secure=True,
                        samesite='Lax',
                        max_age=settings.JWT_REFRESH_TOKEN_EXPIRY_DAYS * 24 * 60 * 60
                    )
    return response

def set_jwt_cookie(response, jwt_token, domain=None):
    # set the jwt token in the response cookies
    response.set_cookie('jwt_token', 
                        domain=domain,
                        key='jwt_token',
                        value=jwt_token,
                        httponly=True,
                        secure=True,
                        samesite='Lax',
                        max_age=settings.JWT_TOKEN_EXPIRY_HOURS * 60 * 60
                    )
    return response

def delete_cookies(response):
    # delete the jwt token and the refresh token from the response cookies
    response.delete_cookie('jwt_token')
    response.delete_cookie('refresh_token')
    return response