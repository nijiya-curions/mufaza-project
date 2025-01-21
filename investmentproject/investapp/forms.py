# forms.py
from django import forms
from .models import CustomUser,Transaction
from django.contrib.auth.hashers import make_password

class SignupForm(forms.ModelForm):
    password = forms.CharField(widget=forms.PasswordInput(attrs={'class': 'input-field'}), label='Password')
    confirm_password = forms.CharField(widget=forms.PasswordInput(attrs={'class': 'input-field'}), label='Confirm Password')
    phone_number = forms.CharField(widget=forms.TextInput(attrs={'class': 'input-field'}))
    address = forms.CharField(widget=forms.Textarea(attrs={'class': 'input-field', 'rows': 3}))

    class Meta:
        model = CustomUser
        fields = ['username', 'first_name', 'last_name', 'password', 'phone_number', 'address']

    def clean(self):
        cleaned_data = super().clean()
        password = cleaned_data.get('password')
        confirm_password = cleaned_data.get('confirm_password')
        if password != confirm_password:
            raise forms.ValidationError("Passwords do not match.")

    def save(self, commit=True):
        user = super().save(commit=False)
        user.password = make_password(self.cleaned_data['password'])  # Hash the password
        if commit:
            user.save()
        return user
    


# Transaction form
from django.contrib.auth import get_user_model

User = get_user_model()  # Use the custom user model if available

class TransactionForm(forms.ModelForm):
    user = forms.ModelChoiceField(
        queryset=User.objects.filter(is_staff=False),  # Exclude admins
        label="Select User"
    ) # Select field for users

    class Meta:
        model = Transaction
        fields = ['user', 'particulars', 'narration', 'amount_type', 'amount']


# investapp/forms.py

from django import forms
from .models import Transaction

class InvestmentForm(forms.ModelForm):
    class Meta:
        model = Transaction
        fields = ['particulars', 'narration', 'amount','amount_type', 'transaction_receipt']









