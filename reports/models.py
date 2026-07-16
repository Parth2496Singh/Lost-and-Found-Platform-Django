from django.db import models
from django.conf import settings
from django_prometheus.models import ExportModelOperationsMixin

# ===================== CATEGORY CHOICES =====================
CATEGORY_CHOICES = [
    ('Phone', 'Phone'),
    ('Wallet', 'Wallet'),
    ('Bag', 'Bag'),
    ('Laptop', 'Laptop'),
    ('Keys', 'Keys'),
    ('Other', 'Other'),
]

# ===================== LOST ITEM MODEL =====================
class LostItems(ExportModelOperationsMixin('lost_item'), models.Model):
    # Link to actual user when JWT/auth is implemented
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, null=True, blank=True)

    name = models.CharField(max_length=50)
    date_lost = models.DateField()
    location = models.TextField(max_length=200)
    description = models.TextField()
    category = models.CharField(max_length=50, choices=CATEGORY_CHOICES, default='Other')

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.name} (Lost)"

# ===================== FOUND ITEM MODEL =====================
class FoundItem(ExportModelOperationsMixin('found_item'), models.Model):
    # Link to actual user when JWT/auth is implemented
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, null=True, blank=True)

    name = models.CharField(max_length=200)
    date_found = models.DateField()
    location = models.CharField(max_length=200)
    description = models.TextField()
    category = models.CharField(max_length=50, choices=CATEGORY_CHOICES, default='Other')

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.name} (Found)"

# ===================== CLAIM MODEL =====================
class ClaimClaim(ExportModelOperationsMixin('claim'), models.Model):
    lost_item = models.ForeignKey(LostItems, on_delete=models.CASCADE)
    found_item = models.ForeignKey(FoundItem, on_delete=models.CASCADE)

    # Claim status: Pending → Approved/Rejected
    status = models.CharField(max_length=20, choices=[
        ("Pending", "Pending"),
        ("Approved", "Approved"),
        ("Rejected", "Rejected")
    ], default="Pending")

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Claim: {self.lost_item.name} ↔ {self.found_item.name} | Status: {self.status}"
