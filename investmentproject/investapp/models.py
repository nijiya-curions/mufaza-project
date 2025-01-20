# models.py
from django.contrib.auth.models import AbstractUser
from django.db import models
from django.contrib.auth import get_user_model
from django.conf import settings
from django.db import models
from django.db.models import Sum

class CustomUser(AbstractUser):
    phone_number = models.CharField(max_length=15)
    address = models.TextField()
    is_approved = models.BooleanField(default=False)  # Only approved users can log in

    def __str__(self):
        return self.username
    
    
# transaction model
class Transaction(models.Model):
    DEBIT_CREDIT_CHOICES = [
        ('debit', 'Debit'),
        ('credit', 'Credit'),
    ]

    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
    ]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='transactions')
    date = models.DateField(auto_now_add=True)
    particulars = models.CharField(max_length=255)
    narration = models.TextField()
    amount_type = models.CharField(max_length=6, choices=DEBIT_CREDIT_CHOICES)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    transaction_receipt = models.ImageField(upload_to='transaction_receipts/', blank=True, null=True)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='pending')  # New field for approval status

    def balance(self):
        debit_total = Transaction.objects.filter(user=self.user, amount_type='debit', status='approved').aggregate(Sum('amount'))['amount__sum'] or 0
        credit_total = Transaction.objects.filter(user=self.user, amount_type='credit', status='approved').aggregate(Sum('amount'))['amount__sum'] or 0
        return credit_total - debit_total

    def __str__(self):
        return f"{self.particulars} - {self.date} - {self.amount_type} - {self.amount} - {self.status}"


