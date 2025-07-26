from datetime import timedelta
import uuid
from django_tenants.models import TenantMixin, DomainMixin
from django.db import models
#  import User  table 
from django.contrib.auth.models import User
from django.contrib.auth.models import AbstractUser
# import settings
from django.conf import settings
from jsonschema import ValidationError
from gymowners.managers import CustomUserManager
from django.contrib.postgres.fields import ArrayField

class Client(TenantMixin):
    created_on = models.DateTimeField(auto_now_add=True)
    updated_on = models.DateTimeField(auto_now=True)
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    gym_name = models.CharField(max_length=100, blank=True, null=True,unique=True)
    gym_uuid = models.UUIDField(default=uuid.uuid4,unique=True, editable=False)
    gym_location = models.CharField(max_length=100, blank=True, null=True)
    gym_phone_number = models.CharField(max_length=15, blank=True, null=True)
    gym_email = models.EmailField(max_length=255, blank=True, null=True)
    latitude = models.DecimalField(max_digits=9, decimal_places=6, blank=True, null=True, help_text="Latitude of the gym location")
    longitude = models.DecimalField(max_digits=9, decimal_places=6, blank=True, null=True, help_text="Longitude of the gym location")
    is_active = models.BooleanField(default=True)
    created_on = models.DateTimeField(auto_now_add=True)
    updated_on = models.DateTimeField(auto_now=True)
    ratings = models.DecimalField(max_digits=3, decimal_places=2, default=0.00, help_text="Average rating of the gym out of 5")
    auto_create_schema = True

    def __str__(self):
        return f"{self.gym_name or 'Unnamed Gym'}"

class Domain(DomainMixin):
    domain = models.SlugField(max_length=100, unique=True)
    subdomain = models.CharField(max_length=100, unique=False, help_text="Subdomain for the tenant, e.g., 'mygym'", null =True, blank=True)
    tenant = models.ForeignKey(Client, on_delete=models.CASCADE, related_name='domains')
    created_on = models.DateTimeField(auto_now_add=True)
    updated_on = models.DateTimeField(auto_now=True)
    def __str__(self):
        return self.domain
    
    def save(self, *args, **kwargs):
        return super().save(*args, **kwargs)
    
    # only one tenant can have a primary domain
    def clean(self):
        if self.is_primary:
            Domain.objects.filter(tenant=self.tenant, is_primary=True).exclude(id=self.id).update(is_primary=False)

class CustomUser(AbstractUser):
    middle_name = models.CharField(max_length=30, blank=True, null=True)
    role = models.CharField(max_length=20, choices=settings.ROLE_CHOICES)
    objects = CustomUserManager()
    phone_number = models.CharField(max_length=15, blank=False, null=False, unique=True)
    email = models.EmailField(max_length=255, unique=True, blank=False, null=False)
    created_on = models.DateTimeField(auto_now_add=True)
    updated_on = models.DateTimeField(auto_now=True)

    def clean(self):
        if not self.email:
            raise ValidationError("Email is required.")
        if not self.phone_number:
            raise ValidationError("Phone number is required.")
        if not self.role:
            raise ValidationError("Role is required.")
        if self.role not in dict(settings.ROLE_CHOICES):
            raise ValidationError(f"Invalid role: {self.role}. Must be one of {dict(settings.ROLE_CHOICES).keys()}.")   
    
    def save(self, *args, **kwargs):
        if self.role == 'superadmin':
            self.is_staff = True
            self.is_superuser = True
        elif self.role == 'admin':
            self.is_staff = True
            self.is_superuser = False
        else:
            self.is_staff = False
            self.is_superuser = False
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.email} ({self.role})"



class GymUserOtherInfo(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    current_gym = models.ForeignKey(Client, on_delete=models.CASCADE, related_name='current_users', help_text="Current gym where the user is registered")
    emergency_contact_number = models.CharField(max_length=15, blank=False, null=False)
    address = models.TextField(blank=False, null=False, help_text="Address of the user")
    batch = models.CharField(max_length=10, choices=settings.BATCH_CHOICES, blank=False, null=False)
    height = models.DecimalField(max_digits=5, decimal_places=2, blank=False, null=False, help_text="Height in cm")
    weight = models.DecimalField(max_digits=5, decimal_places=2, blank=False, null=False, help_text="Weight in kg")
    blood_group = models.CharField(max_length=3, choices=settings.BLOOD_GROUP_CHOICES, blank=False, null=False, help_text="Blood group of the user")
    medical_conditions = models.TextField(blank=False, null=False, help_text="Any known medical conditions")
    fitness_goals = ArrayField(base_field=models.CharField(max_length=50, choices=settings.GOAL_CHOICES),blank=False,default=list,help_text="List of fitness goals (e.g., weight loss, muscle gain, etc.)")
    notes = models.TextField(blank=True, null=True, help_text="Additional notes or preferences")
    attachments = ArrayField(base_field=models.URLField(max_length=200), blank=True, default=list, help_text="List of attachment URLs")
    date_of_birth = models.DateField(null=False, blank=False, help_text="Date of birth in YYYY-MM-DD format")
    gender = models.CharField(max_length=10, choices=settings.GENDER_CHOICES, null=False, blank=False, help_text="Gender of the user")
    created_on = models.DateTimeField(auto_now_add=True)
    updated_on = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True, help_text="Is the user currently active?")
    def clean(self):
        if not self.emergency_contact_number:
            raise ValidationError("Emergency contact number is required.")
        if not self.batch:
            raise ValidationError("Batch is required.")
        if self.height <= 0:
            raise ValidationError("Height must be a positive number.")
        if self.weight <= 0:
            raise ValidationError("Weight must be a positive number.")
        if not self.blood_group:
            raise ValidationError("Blood group is required.")
        if not self.medical_conditions:
            raise ValidationError("Medical conditions are required.")
        if not self.fitness_goals:
            raise ValidationError("At least one fitness goal is required.")
        if len(self.fitness_goals) > 5:
            raise ValidationError("You can only have up to 5 fitness goals.")
        if self.attachments and len(self.attachments) > 5:
            raise ValidationError("You can only have up to 5 attachments.")
        if not self.date_of_birth:
            raise ValidationError("Date of birth is required.")
        if not self.gender:
            raise ValidationError("Gender is required.")

    def __str__(self):
        return f"{self.user.email} - Other Info"

class GymTrainerOtherInfo(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    current_gym = models.ForeignKey(Client, on_delete=models.CASCADE, related_name='current_trainers', help_text="Current gym where the trainer is employed")   
    emergency_contact_number = models.CharField(max_length=15, blank=False, null=False, help_text="Emergency contact number of the trainer")
    date_of_birth = models.DateField(null=False, blank=False, help_text="Date of birth in YYYY-MM-DD format")
    gender = models.CharField(max_length=10, choices=settings.GENDER_CHOICES, null=False, blank=False, help_text="Gender of the user")
    address = models.TextField(blank=False, null=False, help_text="Address of the trainer")
    blood_group = models.CharField(max_length=3, choices=settings.BLOOD_GROUP_CHOICES, blank=False, null=False, help_text="Blood group of the trainer")
    medical_conditions = models.TextField(blank=True, null=True, help_text="Any known medical conditions of the trainer")
    past_experience = models.TextField(blank=True, null=True, help_text="Past experience of the trainer in the fitness industry")
    certifications = models.TextField(blank=True, null=True, help_text="Certifications held by the trainer")
    specialization = ArrayField(base_field=models.CharField(max_length=50, choices=settings.SPECIALIZATION_CHOICES), blank=False, default=list, help_text="List of specializations of the trainer")
    created_on = models.DateTimeField(auto_now_add=True)
    updated_on = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True, help_text="Is the trainer currently active?")
    def clean(self):
        if not self.emergency_contact_number:
            raise ValidationError("Emergency contact number is required.")
        if not self.date_of_birth:
            raise ValidationError("Date of birth is required.")
        if not self.gender:
            raise ValidationError("Gender is required.")
        if not self.address:
            raise ValidationError("Address is required.")
        if not self.blood_group:
            raise ValidationError("Blood group is required.")
        if self.medical_conditions and len(self.medical_conditions) > 500:
            raise ValidationError("Medical conditions cannot exceed 500 characters.")
        if self.past_experience and len(self.past_experience) > 500:
            raise ValidationError("Past experience cannot exceed 500 characters.")
        if self.certifications and len(self.certifications) > 500:
            raise ValidationError("Certifications cannot exceed 500 characters.")
        if self.specializations and len(self.specializations) > 5:
            raise ValidationError("You can only have up to 5 specializations.")

    def __str__(self):
        return f"{self.user.email} - Trainer Info"
    


class TrainerGymHistory(models.Model):
    trainer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='trainer_gym_history'
    )
    gym = models.ForeignKey(Client, on_delete=models.CASCADE, related_name='trainer_history')
    start_date = models.DateField(null=False, blank=False)
    end_date = models.DateField(null=True, blank=True)
    is_active = models.BooleanField(default=True)

    # at a  time for a trainer only one gym can be active
    def clean(self):
        if self.is_active and TrainerGymHistory.objects.filter(trainer=self.trainer, is_active=True).exclude(id=self.id).exists():
            # if there are activated  then deactivate the previous one
            TrainerGymHistory.objects.filter(trainer=self.trainer, is_active=True).exclude(id=self.id).update(is_active=False)  

    def __str__(self):
        return f"{self.trainer.email} - {self.gym.gym_name} History"


class UserGymHistory(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='user_gym_history'
    )
    gym = models.ForeignKey(Client, on_delete=models.CASCADE, related_name='user_history')
    start_date = models.DateField(null=False, blank=False)
    end_date = models.DateField(null=True, blank=True)
    is_active = models.BooleanField(default=True)

    # at a time for a user only one gym can be active
    def clean(self):
        if self.is_active and UserGymHistory.objects.filter(user=self.user, is_active=True).exclude(id=self.id).exists():
            # if there are activated  then deactivate the previous one
            UserGymHistory.objects.filter(user=self.user, is_active=True).exclude(id=self.id).update(is_active=False)
            
    def __str__(self):
        return f"{self.user.email} - {self.gym.gym_name} Membership History"
