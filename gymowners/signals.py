from django.db.models.signals import post_migrate
from django.dispatch import receiver
from django.conf import settings
from gymowners.models import Client, Domain
from django.db.utils import OperationalError, ProgrammingError
from django.contrib.auth import get_user_model
from decouple import config
from django.db import transaction

@transaction.atomic
@receiver(post_migrate)
def create_public_tenant(sender, **kwargs):
    try:
        if not Client.objects.filter(schema_name='public').exists():
            username = config('DJANGO_SUPERUSER_USERNAME')
            email = config('DJANGO_SUPERUSER_EMAIL')
            password = config('DJANGO_SUPERUSER_PASSWORD')
            print("Creating default superuser...")
            User = get_user_model()
            user =User.objects.create_superuser(
                username=username,
                email=email,
                password=password,  
                role='superadmin'  # if your CustomUser has a role field
            )
            client = Client.objects.create(
                schema_name='public',
                gym_name='Main Public Site',
                user=user,
                # paid_until='2099-12-31',
                # on_trial=False
            )
            domain_name = settings.BASE_DOMAIN
            if not Domain.objects.filter(domain=domain_name,is_primary=True).exists():
                Domain.objects.create(
                    domain=domain_name,
                    tenant=client,
                    is_primary=True
                )
    except (OperationalError, ProgrammingError):
        # DB might not be ready yet during first migrate
        pass

