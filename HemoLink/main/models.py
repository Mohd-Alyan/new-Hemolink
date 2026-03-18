from django.contrib.auth.models import User
from django.db import models
from django.utils import timezone


class UserRole(models.TextChoices):
    DONOR = "donor", "Donor"
    REQUESTER = "requester", "Requester"


class BloodType(models.TextChoices):
    A_POS = "A+", "A+"
    A_NEG = "A-", "A-"
    B_POS = "B+", "B+"
    B_NEG = "B-", "B-"
    O_POS = "O+", "O+"
    O_NEG = "O-", "O-"
    AB_POS = "AB+", "AB+"
    AB_NEG = "AB-", "AB-"


class OrganizationType(models.TextChoices):
    HOSPITAL = "hospital", "Hospital"
    BLOOD_BANK = "blood_bank", "Blood Bank"


class RequestPriority(models.TextChoices):
    NORMAL = "normal", "Normal"
    HIGH = "high", "High"
    URGENT = "urgent", "Urgent"


class RequestStatus(models.TextChoices):
    OPEN = "open", "Open"
    MATCHED = "matched", "Matched"
    FULFILLED = "fulfilled", "Fulfilled"
    CANCELLED = "cancelled", "Cancelled"


class MatchStatus(models.TextChoices):
    NOTIFIED = "notified", "Notified"
    ACCEPTED = "accepted", "Accepted"
    DECLINED = "declined", "Declined"
    COMPLETED = "completed", "Completed"


class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="profile")
    role = models.CharField(max_length=20, choices=UserRole.choices)
    phone_number = models.CharField(max_length=20, blank=True)
    address = models.CharField(max_length=255, blank=True)
    latitude = models.DecimalField(max_digits=9, decimal_places=6, blank=True, null=True)
    longitude = models.DecimalField(max_digits=9, decimal_places=6, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.user.username} ({self.role})"


class DonorProfile(models.Model):
    user_profile = models.OneToOneField(UserProfile, on_delete=models.CASCADE, related_name="donor_profile")
    full_name = models.CharField(max_length=150)
    blood_type = models.CharField(max_length=3, choices=BloodType.choices)
    date_of_birth = models.DateField()
    weight_kg = models.DecimalField(max_digits=5, decimal_places=2)
    gender = models.CharField(max_length=20)
    is_available = models.BooleanField(default=True)
    last_donation_date = models.DateField(blank=True, null=True)

    @property
    def age(self):
        today = timezone.now().date()
        return today.year - self.date_of_birth.year - (
            (today.month, today.day) < (self.date_of_birth.month, self.date_of_birth.day)
        )

    def __str__(self):
        return f"{self.full_name} - {self.blood_type}"


class RequesterOrganization(models.Model):
    user_profile = models.OneToOneField(UserProfile, on_delete=models.CASCADE, related_name="requester_organization")
    organization_name = models.CharField(max_length=150)
    organization_type = models.CharField(max_length=20, choices=OrganizationType.choices)

    def __str__(self):
        return self.organization_name


class BloodRequest(models.Model):
    requester = models.ForeignKey(RequesterOrganization, on_delete=models.CASCADE, related_name="blood_requests")
    blood_type = models.CharField(max_length=3, choices=BloodType.choices)
    units_required = models.PositiveIntegerField()
    priority = models.CharField(max_length=20, choices=RequestPriority.choices, default=RequestPriority.NORMAL)
    status = models.CharField(max_length=20, choices=RequestStatus.choices, default=RequestStatus.OPEN)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    fulfilled_at = models.DateTimeField(blank=True, null=True)

    def __str__(self):
        return f"Request #{self.id} - {self.blood_type}"


class DonationMatch(models.Model):
    blood_request = models.ForeignKey(BloodRequest, on_delete=models.CASCADE, related_name="matches")
    donor = models.ForeignKey(DonorProfile, on_delete=models.CASCADE, related_name="matches")
    status = models.CharField(max_length=20, choices=MatchStatus.choices, default=MatchStatus.NOTIFIED)
    is_selected = models.BooleanField(default=False)
    selected_at = models.DateTimeField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    responded_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        unique_together = ("blood_request", "donor")

    def __str__(self):
        return f"Match #{self.id} - Request {self.blood_request_id} / Donor {self.donor_id}"


class InboxNotification(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="inbox_notifications")
    blood_request = models.ForeignKey(BloodRequest, on_delete=models.CASCADE, related_name="notifications", blank=True, null=True)
    message = models.CharField(max_length=255)
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.user.username} - {self.message}"
