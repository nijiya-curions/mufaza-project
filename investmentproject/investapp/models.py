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
        return f"User: {self.user.username}, {self.user.first_name} {self.user.last_name}, {self.user.email}, {self.user.phone_number}, {self.user.address} | Transaction: {self.particulars} - {self.date} - {self.amount_type} - {self.amount} - {self.status}"





class InvestmentProject(models.Model):
    RETURN_TYPE_CHOICES = [
        ('fixed', 'Fixed'),
        ('variable', 'Variable'),
    ]
    STATUS_CHOICES = [
        ('active', 'Active'),
        ('inactive', 'Inactive'),
    ]
    
    project_name = models.CharField(max_length=255)
    return_type = models.CharField(max_length=8, choices=RETURN_TYPE_CHOICES)
    fixed_return_percentage = models.DecimalField(
        max_digits=5, decimal_places=2, blank=True, null=True, 
        help_text="Required if return type is Fixed"
    )
    min_return_percentage = models.DecimalField(
        max_digits=5, decimal_places=2, blank=True, null=True, 
        help_text="Required if return type is Variable"
    )
    max_return_percentage = models.DecimalField(
        max_digits=5, decimal_places=2, blank=True, null=True, 
        help_text="Required if return type is Variable"
    )
    status = models.CharField(
        max_length=8, choices=STATUS_CHOICES, default='active'
    )  

    def __str__(self):
        return f"{self.project_name} ({self.return_type}) - {self.status}"

    def clean(self):
        """Ensure correct percentage fields are filled based on return type"""
        from django.core.exceptions import ValidationError
        
        if self.return_type == 'fixed' and self.fixed_return_percentage is None:
            raise ValidationError("Fixed return percentage is required for fixed return type.")
        if self.return_type == 'variable':
            if self.min_return_percentage is None or self.max_return_percentage is None:
                raise ValidationError("Minimum and Maximum return percentages are required for variable return type.")
            if self.min_return_percentage > self.max_return_percentage:
                raise ValidationError("Minimum return percentage cannot be greater than Maximum return percentage.")

        super().clean()

# project assigning for users

class UserProjectAssignment(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='assigned_projects'
    )
    project = models.ForeignKey(
        InvestmentProject,
        on_delete=models.CASCADE,
        related_name='assigned_users'
    )
    return_percentage = models.DecimalField(
        max_digits=5, decimal_places=2,blank=True, null=True,
        help_text="Custom return percentage for this user in this project"
    )

    def get_effective_return(self):
        """Return the assigned percentage or default to project's percentage."""
        if self.return_percentage is not None:
            return self.return_percentage
        return self.project.fixed_return_percentage if self.project.return_type == 'fixed' else self.project.min_return_percentage

    def __str__(self):
        return f"{self.user.username} - {self.project.project_name} ({self.get_effective_return()}%)"
    
    

    
# documents

class UserDocument(models.Model):
    DOCUMENT_TYPES = [
        ('aadhaar', 'Aadhaar Card'),
        ('voter_id', 'Voter ID'),
        ('passbook', 'Passbook'),
        ('other', 'Other')
    ]
    
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='documents')
    document_type = models.CharField(max_length=20, choices=DOCUMENT_TYPES)
    file = models.FileField(upload_to='user_documents/')
    uploaded_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"{self.user.username} - {self.get_document_type_display()}"


