# forms.py
from django import forms
from .models import CustomUser,Transaction,InvestmentProject
from django.contrib.auth.hashers import make_password
from django.core.validators import RegexValidator


class SignupForm(forms.ModelForm):
    # Adding the RegexValidator for phone_number to only accept numbers
    phone_number = forms.CharField(
    widget=forms.TextInput(attrs={'class': 'input-field'}),
    validators=[RegexValidator(r'^\d{7,15}$', 'Enter a valid phone number with 7 to 15 digits.')],
    label='Phone Number'
)
    
    password = forms.CharField(widget=forms.PasswordInput(attrs={'class': 'input-field'}), label='Password')
    confirm_password = forms.CharField(widget=forms.PasswordInput(attrs={'class': 'input-field'}), label='Confirm Password')
    address = forms.CharField(widget=forms.Textarea(attrs={'class': 'input-field', 'rows': 3}))

    class Meta:
        model = CustomUser
        fields = ['username', 'first_name', 'last_name', 'email', 'password', 'phone_number', 'address']

    def clean(self):
        cleaned_data = super().clean()
        password = cleaned_data.get('password')
        confirm_password = cleaned_data.get('confirm_password')

        if password != confirm_password:
            raise forms.ValidationError("Passwords do not match.")

        # Check if the phone number already exists
        phone_number = cleaned_data.get('phone_number')
        if CustomUser.objects.filter(phone_number=phone_number).exists():
            raise forms.ValidationError("This phone number is already registered.")

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
    class Meta:
        model = Transaction
        fields = ['user', 'particulars', 'narration', 'amount_type', 'amount']


# investapp/forms.py

class InvestmentForm(forms.ModelForm):
    class Meta:
        model = Transaction
        fields = ['particulars', 'narration', 'amount','amount_type', 'transaction_receipt']



# update profile form

class UserProfileUpdateForm(forms.ModelForm):
    password = forms.CharField(
        required=False,
        widget=forms.PasswordInput(attrs={'class': 'input-field'}),
        help_text="Leave blank if you don't want to change the password.",
    )

    class Meta:
        model = get_user_model()
        fields = ['username', 'first_name', 'last_name', 'email', 'phone_number', 'address', 'password']

    def save(self, commit=True):
        user = super().save(commit=False)

        # Get the new password entered in the form
        new_password = self.cleaned_data.get('password')

        # Only update the password if a new one is provided
        if new_password:
            user.set_password(new_password)  # Hash and set the password
        else:
            # Retain the existing password by re-fetching it from the database
            user.password = get_user_model().objects.get(pk=user.pk).password

        if commit:
            user.save()

        return user


# project 

from django import forms
from .models import InvestmentProject

class InvestmentProjectForm(forms.ModelForm):
    return_type = forms.ChoiceField(
        choices=[("fixed", "Fixed"), ("variable", "Variable")],
        widget=forms.Select(attrs={'class': 'form-select custom-input'}),
        initial="fixed"  # 👈 Set default to "fixed"
    )

    class Meta:
        model = InvestmentProject
        fields = ['project_name', 'return_type', 'fixed_return_percentage', 'min_return_percentage', 'max_return_percentage', 'status']

        widgets = {
            'project_name': forms.TextInput(attrs={
                'class': 'form-control custom-input',
                'placeholder': 'Enter project name...'
            }),
            'return_type': forms.Select(attrs={'class': 'form-select custom-input'}),
            'fixed_return_percentage': forms.NumberInput(attrs={
                'class': 'form-control custom-input',
                'placeholder': 'Enter fixed return %'
            }),
            'min_return_percentage': forms.NumberInput(attrs={
                'class': 'form-control custom-input',
                'placeholder': 'Min return %'
            }),
            'max_return_percentage': forms.NumberInput(attrs={
                'class': 'form-control custom-input',
                'placeholder': 'Max return %'
            }),
            'status': forms.Select(attrs={'class': 'form-select custom-input'}),
        }

    def clean(self):
        cleaned_data = super().clean()
        return_type = cleaned_data.get("return_type")

        # Reset values that are not needed
        if return_type == "fixed":
            cleaned_data["min_return_percentage"] = None
            cleaned_data["max_return_percentage"] = None
        elif return_type == "variable":
            cleaned_data["fixed_return_percentage"] = None

            min_return = cleaned_data.get("min_return_percentage")
            max_return = cleaned_data.get("max_return_percentage")

            if min_return is None or max_return is None:
                raise forms.ValidationError("Min and Max return percentages are required for variable return type.")
            if min_return > max_return:
                raise forms.ValidationError("Minimum return percentage cannot be greater than Maximum return percentage.")

        return cleaned_data



# assigning project
from django import forms
from .models import UserProjectAssignment, CustomUser, InvestmentProject

class UserProjectAssignmentForm(forms.ModelForm):
    user = forms.ModelChoiceField(queryset=CustomUser.objects.all(), widget=forms.HiddenInput())
    project = forms.ModelChoiceField(queryset=InvestmentProject.objects.all(), widget=forms.Select(attrs={'class': 'form-select'}))
    return_percentage = forms.DecimalField(required=False, widget=forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'Optional Return %'}))

    class Meta:
        model = UserProjectAssignment
        fields = ['user', 'project', 'return_percentage']


# document
from django import forms
from .models import UserDocument

class UserDocumentForm(forms.ModelForm):
    class Meta:
        model = UserDocument
        fields = ['document_type', 'file']
