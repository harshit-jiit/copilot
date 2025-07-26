from django.db import models
from django.forms import ValidationError
from django.contrib.postgres.fields import ArrayField
from django.conf import settings
from gymowners.models import Client, CustomUser, GymTrainerOtherInfo, GymUserOtherInfo,Domain
from datetime import timedelta
from django.db import connection
from uuid import uuid4
from uuid import UUID as UUIDField
import uuid
from django.db import models
from enum import Enum
from django_tenants.utils import schema_context

def validate_gym_owner(user_id):
    """Validate gym owner-related business logic."""
    with schema_context(settings.PUBLIC_SCHEMA_NAME):
        try:
            user = CustomUser.objects.get(id=user_id)
            if not user.is_active:
                raise ValidationError("User must be active.")
        except CustomUser.DoesNotExist:
            raise ValidationError("User does not exist.")
        except Client.DoesNotExist:
            raise ValidationError("Gym owner information not found.")

def validate_user_entry(user_id):
    """Validate user-related business logic."""
    with schema_context(settings.PUBLIC_SCHEMA_NAME):
        try:
            user = CustomUser.objects.get(id=user_id)
            user_current_gym = GymUserOtherInfo.objects.get(user=user)
        except CustomUser.DoesNotExist:
            raise ValidationError("User does not exist.")
        except GymUserOtherInfo.DoesNotExist:
            raise ValidationError("Gym user information not found.")
    schema_name = connection.schema_name
    if schema_name != user_current_gym.current_gym.schema_name:
        raise ValidationError("User must belong to the same gym as the membership.")
    if user.role != settings.ROLE_GYM_USER:
        raise ValidationError("User must have the role of gym user.")
    if not user.is_active:
        raise ValidationError("User must be active.")

def validate_gym_trainer(trainer_id):
    """Validate gym trainer-related business logic."""
    with schema_context(settings.PUBLIC_SCHEMA_NAME):
        try:
            user = CustomUser.objects.get(id=trainer_id)
            user_current_gym = GymTrainerOtherInfo.objects.get(user=user)
        except CustomUser.DoesNotExist:
            raise ValidationError("Gym trainer does not exist.")
        except GymTrainerOtherInfo.DoesNotExist:
            raise ValidationError("Gym trainer information not found.")
    schema_name = connection.schema_name
    if schema_name != user_current_gym.current_gym.schema_name:
        raise ValidationError("Gym trainer does not belong to the same gym.")
    if user.role != settings.ROLE_GYM_TRAINER:
        raise ValidationError("Gym trainer must have the role of gym trainer.")
    if not user.is_active:
        raise ValidationError("Gym trainer must be active.")

class GymPackage(models.Model):
    package_name = models.CharField(max_length=100, unique=True)
    package_price = models.DecimalField(max_digits=10, decimal_places=2)
    package_duration = models.IntegerField(help_text="Duration in days", blank=False, null=False)
    package_description = models.TextField(blank=True, null=True)
    created_on = models.DateTimeField(auto_now_add=True)
    updated_on = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True)
    def clean(self):
        if self.package_duration <= 0:
            raise ValidationError("Package duration must be a positive integer.")
        if self.package_price < 0:
            raise ValidationError("Package price cannot be negative.")

    def __str__(self):
        return f"{self.package_name} - {self.package_price} ({self.package_duration} days)"



class GymActivityType(models.Model):
    type_name = models.CharField(max_length=50, default='cardio' , help_text="Name of the activity type", blank=False, null=False,unique=True)
    created_on = models.DateTimeField(auto_now_add=True)
    updated_on = models.DateTimeField(auto_now=True)
    type_description = models.TextField(blank=True, null=True, help_text="Description of the activity type")
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.type_name

class GymActivity(models.Model):
    activity_name = models.CharField(max_length=100, help_text="Name of the activity", blank=False, null=False, unique=True)
    activity_type = models.ForeignKey(GymActivityType, on_delete=models.SET_NULL, null=True, blank=True, related_name='activities')
    activity_description = models.TextField(blank=True, null=True)
    repr =models.JSONField(
        help_text="Representation of the activity, can be used for frontend display",
        blank=True,
        null=True
    )
    timing = models.DecimalField(max_digits=5, decimal_places=2, help_text="Number of hours for the activity", blank=False, null=False)
    days = ArrayField(
        models.CharField(max_length=10, choices=settings.ACTIVITY_DAYS),
        help_text="Days of the week when the activity is available",
        blank=True,
        null=True
    )
    intensity_level = models.CharField(
        max_length=10,
        choices= settings.ACTIVITY_INTENSITY_LEVELS,
        help_text="Intensity level of the activity",
        blank=False,
        null=False
    )
    max_participants = models.IntegerField(help_text="Maximum number of participants allowed", blank=False, null=False)
    notes = models.TextField(
        help_text="Additional notes or instructions for the activity",
        blank=True,
        null=True
    )
    created_on = models.DateTimeField(auto_now_add=True)
    updated_on = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True)

    def clean(self):
        if self.timing <= 0:
            raise ValidationError("Timing must be a positive number.")
        if self.max_participants <= 0:
            raise ValidationError("Maximum participants must be a positive integer.")
    def __str__(self):
        return f"{self.activity_name} - {self.no_of_hours} hours ({self.max_participants} participants max)"


class GymPackageActivity(models.Model):
    """
    This model represents the many-to-many relationship between GymPackage and GymActivity.
    It allows a package to have multiple activities and an activity to be part of multiple packages.
    """
    gym_package = models.ForeignKey(GymPackage, on_delete=models.CASCADE, related_name='activities')
    activity = models.ForeignKey(GymActivity, on_delete=models.CASCADE, related_name='packages')
    created_on = models.DateTimeField(auto_now_add=True)
    updated_on = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True)
    def clean(self):
        if not self.gym_package or not self.activity:
            raise ValidationError("Both package and activity must be provided.")
        if self.gym_package.is_active is False or self.activity.is_active is False:
            raise ValidationError("Both package and activity must be active.")
        if self.gym_package.is_active is False:
            raise ValidationError("Package must be active.")
        if self.activity.is_active is False:
            raise ValidationError("Activity must be active.")

    def __str__(self):
        return f"{self.gym_package.package_name} - {self.activity.activity_name}"


class GymActivityAssignedTrainer(models.Model):
    """
    This model represents the many-to-many relationship between GymActivity and GymTrainer.
    It allows an activity to have multiple trainers and a trainer to be assigned to multiple activities.
    """
    activity = models.ForeignKey(GymActivity, on_delete=models.CASCADE, related_name='assigned_trainers')
    trainer = models.BigIntegerField(
        verbose_name="Trainer user ID",
        help_text="ID of the trainer assigned to the activity",
        blank=False,
        null=False
    )
    created_on = models.DateTimeField(auto_now_add=True)
    updated_on = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True)

    def clean(self):
        activity_data = GymActivity.objects.get(id=self.activity.id)
        if activity_data.is_active is False:
            raise ValidationError("Activity must be active.")
        validate_gym_trainer(self.trainer)

    def __str__(self):
        return f"{self.activity.activity_name} - {self.trainer}"


class GymMember(models.Model):
    user_id = models.BigIntegerField(
        verbose_name="User ID",
        help_text="ID of the user who is a member of the gym",
        blank=False,
        null=False
    )

    trainer_id = models.BigIntegerField(
        verbose_name="Trainer user ID",
        help_text="ID of the trainer assigned to the member",
        blank=True,
        null=True
    )
    membership_start_date = models.DateTimeField()
    membership_end_date = models.DateTimeField(null=True, blank=True)
    referred_by = models.BigIntegerField(
        verbose_name="Referred by user ID",
        help_text="ID of the user who referred this member",
        blank=True,
        null=True
    )
    package = models.ForeignKey(GymPackage, on_delete=models.CASCADE, null=True, blank=True)
    membership_status = models.CharField(max_length=20, choices=settings.MEMBERSHIP_STATUS_CHOICES, default='active', help_text="Status of the membership")
    created_on = models.DateTimeField(auto_now_add=True)
    updated_on = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True)
    def save(self, *args, **kwargs):
        if self.referred_by:
            try:
                referrer = CustomUser.objects.get(id=self.referred_by)
            except CustomUser.DoesNotExist:
                raise ValidationError("Invalid referrer ID.")

        if not self.membership_end_date and self.package:
            self.membership_end_date = self.membership_start_date + timedelta(days=self.package.package_duration)
        elif not self.package and not self.membership_end_date:
            raise ValidationError("Either package or membership end date must be provided.")
        if self.membership_end_date < self.membership_start_date:
            raise ValidationError("Membership end date cannot be before the start date.")
        #validation of trainer 

        validate_gym_trainer(self.trainer_id)
        validate_user_entry(self.user_id)        

        active_membership = GymMember.objects.filter(user_id=self.user_id, membership_status='active').first()
        if active_membership:
            active_membership.membership_status = 'inactive'
            active_membership.save()

        super().save(*args, **kwargs)
    
    def __str__(self):
        return f"{CustomUser.objects.get(id=self.user_id).email}  membership"
    # either package can be null or blank or end date can be null or blank create a rule for this
    def clean(self):
        if not self.package and not self.membership_end_date:
            raise ValidationError("Either package or membership end date must be provided.")


class LoginSession(models.Model):
    user_id = models.BigIntegerField(
        verbose_name="User ID",
        help_text="ID of the user who is logged in",
        blank=False,
        null=False
    )
    login_time = models.DateTimeField(auto_now_add=True)
    logout_time = models.DateTimeField(null=True, blank=True)
    jwt_created_at = models.DateTimeField()
    jwt_expires_at = models.DateTimeField()
    refresh_created_at = models.DateTimeField()
    refresh_expires_at = models.DateTimeField()
    jwt_token = models.TextField(null=True, blank=True)
    refresh_token = models.TextField(null=True, blank=True)
    domain_id = models.BigIntegerField(
        verbose_name="Domain ID",
        help_text="ID of the domain where the user is logged in",
        blank=True,
        null=True,
        default=None
    )

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        # Ensure the user exists and is active
        validate_gym_owner(self.user_id)

        if self.domain_id:
            with schema_context(settings.PUBLIC_SCHEMA_NAME):
                domain = Domain.objects.filter(id=self.domain_id, is_primary=True).first()
                if not domain:
                    raise ValidationError("Invalid domain ID.")
        
        # Ensure the login time is before the logout time if logout time is provided
        if self.logout_time and self.login_time >= self.logout_time:
            raise ValidationError("Login time must be before logout time.")
        
    def __str__(self):
        return f"Session for user {self.user} at {self.login_time} - {self.logout_time if self.logout_time else 'Active'}"


class GymMembersCustomActivity(models.Model):
    user =  models.BigIntegerField(
        verbose_name="User ID",
        help_text="ID of the user who is logged in",
        blank=False,
        null=False
    )
    activity =  models.ForeignKey(GymActivity, on_delete=models.CASCADE, related_name='activities')
    created_on = models.DateTimeField(auto_now_add=True)
    updated_on = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True)

    def save(self, *args, **kwargs):
        if self.activity.is_active is False:
            raise ValidationError("Both activity and trainer must be active.")
        # Ensure the user exists and is active 
        validate_user_entry(self.user)
  
        super().save(*args, **kwargs)


class Attendance(models.Model):
    user = models.BigIntegerField(
        verbose_name="User ID",
        help_text="ID of the user who is attending",
        blank=False,
        null=False
    )
    punch_in_time = models.DateTimeField(auto_now_add=True)
    punch_out_time = models.DateTimeField(null=True, blank=True)
    latitude = models.DecimalField(max_digits=9, decimal_places=6, blank=True, null=True, help_text="Latitude of the attendance location")
    longitude = models.DecimalField(max_digits=9, decimal_places=6, blank=True, null=True, help_text="Longitude of the attendance location")
    is_active = models.BooleanField(default=True)
    year = models.IntegerField(blank=True, null=True, help_text="Year of the attendance record")
    week_of_year = models.IntegerField(blank=True, null=True, help_text="Week of the year for the attendance record")    
    created_on = models.DateTimeField(auto_now_add=True)
    updated_on = models.DateTimeField(auto_now=True)

    def save(self, *args, **kwargs):
        if not self.latitude or not self.longitude:
            raise ValidationError("Latitude and longitude must be provided.")
        
        if self.punch_out_time and self.punch_in_time >= self.punch_out_time:
            raise ValidationError("Punch-in time must be before punch-out time.")
        
        validate_user_entry(self.user)
        # Set year and week_of_year if not provided
        if not self.year or not self.week_of_year:
            from datetime import datetime
            now = datetime.now()
            self.year = self.punch_in_time.year if not self.year else self.year
            self.week_of_year = self.punch_in_time.isocalendar()[1] if not self.week_of_year else self.week_of_year
        super().save(*args, **kwargs)
    def __str__(self):
        return f"Attendance for {self.user} at {self.punch_in_time} - {self.punch_out_time if self.punch_out_time else 'Active'}"
    

# Enums for Payment Method and Status
class PaymentMethod(Enum):
    CASH = 'cash'
    CARD = 'card'
    BANK_TRANSFER = 'bank_transfer'
    UPI = 'upi'
    OTHER = 'other'

    @classmethod
    def choices(cls):
        return [(key.value, key.name) for key in cls]

class PaymentStatus(Enum):
    PENDING = 'pending'
    PAID = 'paid'
    FAILED = 'failed'
    REFUNDED = 'refunded'

    @classmethod
    def choices(cls):
        return [(key.value, key.name) for key in cls]

class Payment(models.Model):
    payment_id = models.UUIDField(default=uuid.uuid4, editable=False, unique=True, primary_key=True)
    user = models.BigIntegerField(
        verbose_name="User ID",
        help_text="ID of the user who is attending",
        blank=False,
        null=False
    )
    invoice = models.CharField(
        max_length=100,
        unique=True,
        db_index=True,
        help_text="Unique invoice number for the payment"
    )
    amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0.00,
    )
    tax_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,   
        default=0.00
    )
    payment_date = models.DateTimeField(
        db_index=True,
        help_text="Date and time of the payment"
    )
    payment_method = models.CharField(
        max_length=20,
        choices=PaymentMethod.choices(),
        default=PaymentMethod.CASH.value,
        help_text="Method used for payment"
    )
    status = models.CharField(
        max_length=20,
        choices=PaymentStatus.choices(),
        default=PaymentStatus.PENDING.value,
        db_index=True,
        help_text="Current status of the payment"
    )
    remarks = models.TextField(
        blank=True,
        null=True,
        help_text="Additional notes about the payment"
    )
    transaction_reference_id = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        unique=True,
        db_index=True,
        help_text="Unique transaction ID from payment gateway, if applicable"
    )
    created_on = models.DateTimeField(auto_now_add=True, db_index=True)
    modified_on = models.DateTimeField(auto_now=True)

    def clean(self):
        """Validate model fields before saving."""
        # Ensure payment_date is not in the future
        from datetime import datetime
        if self.payment_date > datetime.now().astimezone():
            raise ValidationError("Payment date cannot be in the future.")

        # Ensure tax_amount is reasonable relative to amount
        if self.tax_amount > self.amount:
            raise ValidationError("Tax amount cannot exceed the payment amount.")

        # Ensure transaction_reference_id is provided for non-cash payments
        if self.payment_method != PaymentMethod.CASH.value and not self.transaction_reference_id:
            raise ValidationError("Transaction reference ID is required for non-cash payments.")

    def save(self, *args, **kwargs):
        """Custom save method with validation."""
        # Run field validators
        self.full_clean()  # Calls clean() and field validators
        # Run custom user validation
        validate_user_entry(self.user)
        super().save(*args, **kwargs)

    class Meta:
        indexes = [
            models.Index(fields=['payment_date', 'status']),
            models.Index(fields=['user', 'payment_date']),
        ]
        ordering = ['-payment_date']

    def __str__(self):
        return f"Payment {self.payment_id} - {self.amount} ({self.status})"


class UserProvidedRatings(models.Model):
    user = models.BigIntegerField(
        verbose_name="User ID",
        help_text="ID of the user who is providing the rating",
        blank=False,
        null=False
    )
    user_rating = models.DecimalField(max_digits=3, decimal_places=2, default=0.00, help_text="Rating given by the user out of 5")
    review = models.TextField(blank=True, null=True, help_text="Review given by the user")
    created_on = models.DateTimeField(auto_now_add=True)
    updated_on = models.DateTimeField(auto_now=True)

    def clean(self):
        if self.user_rating < 0 or self.user_rating > 5:
            raise ValidationError("Rating must be between 0 and 5.")
        if not self.review:
            raise ValidationError("Review is required.")
        if len(self.review) > 500:
            raise ValidationError("Review cannot exceed 500 characters.")
        if UserProvidedRatings.objects.filter(user=self.user, gym=self.gym).exists():
            raise ValidationError("You have already rated this gym.")
        validate_user_entry(self.user)

    def __str__(self):
        return f"{self.user.email} - {self.gym_client.gym_name} Rating"