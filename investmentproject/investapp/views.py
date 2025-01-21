# views.py
from django.shortcuts import render, redirect,get_object_or_404
from django.contrib.auth import authenticate, login
from django.contrib.auth.decorators import login_required,user_passes_test
from .forms import SignupForm,TransactionForm,InvestmentForm
from .models import CustomUser,Transaction
from django.contrib import messages
from django.contrib.auth import logout
from django.contrib.auth.models import User
from django.contrib.auth import get_user_model
from django.db.models import Sum
from django.views.generic import ListView
from django.db import models
from django.http import HttpResponseForbidden
from django.contrib.messages import get_messages
from decimal import Decimal
from .models import CustomUser, Transaction




# home page
def home(request):
    return render(request, 'home.html')


# signup form
def signup_view(request):
    if request.method == 'POST':
        form = SignupForm(request.POST)
        if form.is_valid():
            user = form.save(commit=False)  # Don't save yet, so we can set `is_approved` to False
            user.is_approved = False  # By default, set new users as not approved
            user.save()  # Save user to the database

            messages.success(request, "Your account has been created. Please wait for approval.")
            return redirect('login')  # Redirect to login after successful signup
    else:
        form = SignupForm()

    return render(request, 'signup.html', {'form': form})



# login for all
def login_view(request):
    if request.method == 'POST':
        username = request.POST['username']
        password = request.POST['password']
        user = authenticate(request, username=username, password=password)
        
        if user is not None:
            if not user.is_approved:  # Check if user is approved
                return render(request, 'login.html', {'error': 'Your account is awaiting approval by an administrator.'})
            
            # Check if user is a developer with specific password
            if user.username == 'developer' and user.check_password('SecurePassword2025!'):
                login(request, user)
                return redirect('/pineapplepie/')  # Redirect to Django admin interface for the developer
            
            # Check if user is a superuser
            if user.is_superuser:
                login(request, user)
                return redirect('transaction_list')  # Redirect for superusers
            
            # Default redirection for normal users
            login(request, user)
            return redirect('dashboard')  # Redirect for normal users
            
        else:
            return render(request, 'login.html', {'error': 'Invalid credentials'})
    
    return render(request, 'login.html')


# logout

def logout_view(request):
    logout(request)
    return redirect('login')



# Admin view to list all users

# Check if user is superuser
def superuser_required(user):
    return user.is_authenticated and user.is_superuser

@user_passes_test(superuser_required)
def admin_user_list(request):
    User = get_user_model()
    users = User.objects.exclude(username='developer')  # Exclude the developer user by username

    if request.method == 'POST':
        user_id = request.POST.get('user_id')
        action = request.POST.get('action')

        try:
            user = User.objects.get(id=user_id)
        except User.DoesNotExist:
            messages.error(request, "User not found.")
            return redirect('admin-user-list')

        if action == 'activate':
            user.is_approved = True  # Use is_active if not using custom field
        elif action == 'deactivate':
            user.is_approved = False
        else:
            messages.error(request, "Invalid action.")
            return redirect('admin-user-list')

        user.save()
        messages.success(request, f"User {user.username} status updated.")

    return render(request, 'manage_users.html', {'users': users})



# admin trasacton creation
# Get the custom user model
CustomUser = get_user_model()

@login_required
@user_passes_test(lambda u: u.is_staff)  # Only admin can access
def create_transaction(request):
    if request.method == 'POST':
        form = TransactionForm(request.POST, request.FILES)
        if form.is_valid():
            transaction = form.save(commit=False)  # Do not save yet
            transaction.status = 'approved'  # Automatically approve the transaction
            
            # Set the user for the transaction (if the admin is creating for a specific user)
            user_id = request.POST.get('user')  # Assuming you pass the user_id as 'user' in the form
            try:
                user = CustomUser.objects.get(id=user_id)  # Fetch the user from CustomUser model
                transaction.user = user  # Set the user for the transaction
            except CustomUser.DoesNotExist:
                messages.error(request, "Selected user does not exist.")
                return redirect('create_transaction')

            transaction.save()  # Save the transaction
            messages.success(request, "Transaction created and approved successfully.")
            return redirect('transaction_list')
    else:
        form = TransactionForm()

    # Clear existing messages
    storage = get_messages(request)
    for _ in storage:
        pass  # Accessing storage clears the messages

    return render(request, 'create_transaction.html', {'form': form})



#  admin transaction list
# Check if the user is an admin (superuser)
def admin_required(user):
    return user.is_authenticated and user.is_staff

@user_passes_test(admin_required, login_url='login')
def transaction_list(request):
    # Get all transactions (to display in the table)
    all_transactions = Transaction.objects.all()

    # Filter only approved transactions (to calculate totals)
    approved_transactions = all_transactions.filter(status='approved')

    # Calculate debit and credit totals for approved transactions
    debit_total = approved_transactions.filter(amount_type='debit').aggregate(Sum('amount'))['amount__sum'] or 0
    credit_total = approved_transactions.filter(amount_type='credit').aggregate(Sum('amount'))['amount__sum'] or 0

    # Assuming all credited amounts are the initial investment
    initial_investment = credit_total
    total_amount = initial_investment - debit_total  # Total returns = Credits - Debits

    return render(request, 'transaction_list.html', {
        'transactions': all_transactions,  # Send all transactions to the template
        'credit_total': credit_total,      # Totals from approved transactions
        'total_amount': total_amount,
        'total_withdrawal': debit_total,
    })



# admin approval and rejection
@login_required
@user_passes_test(lambda user: user.is_staff)
def approve_transaction(request, transaction_id):
    if request.method == 'POST':
        transaction = get_object_or_404(Transaction, id=transaction_id)
        transaction.status = 'approved'
        transaction.save()
        return redirect('transaction_list')

@login_required
@user_passes_test(lambda user: user.is_staff)
def reject_transaction(request, transaction_id):
    if request.method == 'POST':
        transaction = get_object_or_404(Transaction, id=transaction_id)
        transaction.status = 'rejected'
        transaction.save()
        return redirect('transaction_list')
    
# admin user dahsboard

def decimal_to_float(value):
    if isinstance(value, Decimal):
        return float(value)
    return value

@login_required
@user_passes_test(lambda user: user.is_staff)
def admin_user_home(request, user_id=None):
    users = CustomUser.objects.filter(is_staff=False, is_superuser=False)

    user_data = []
    for user in users:
        transactions = Transaction.objects.filter(user=user)
        debit_total = transactions.filter(amount_type='debit').aggregate(Sum('amount'))['amount__sum'] or 0
        credit_total = transactions.filter(amount_type='credit').aggregate(Sum('amount'))['amount__sum'] or 0
        total_returns = credit_total - debit_total
        user_data.append({
            'username': user.username,
            'user_id': user.id,
            'debit_total': decimal_to_float(debit_total),
            'credit_total': decimal_to_float(credit_total),
            'total_returns': decimal_to_float(total_returns),
            'status': 'Active' if total_returns > 0 else 'Inactive',
        })

    # If user_id is provided, retrieve selected user and their ledger
    ledger_data = None
    selected_user = None
    if user_id:
        selected_user = get_object_or_404(CustomUser, id=user_id)
        ledger_data = Transaction.objects.filter(user=selected_user).order_by('-date')

    return render(request, 'admin-user-dashboard.html', {
        'user_data': user_data,
        'ledger_data': ledger_data,
        'selected_user': selected_user,
    })



# for users creating transaction view 

@login_required
def manage_investment(request):
    if request.method == 'POST':
        form = InvestmentForm(request.POST, request.FILES)
        if form.is_valid():
            transaction = form.save(commit=False)
            transaction.user = request.user  # Assign the logged-in user
            transaction.save()
            messages.success(request, "Transaction created successfully!")
            # Render the current page to show the message
            return render(request, 'manage_investment.html', {'form': InvestmentForm()})
    else:
        form = InvestmentForm()
    
    return render(request, 'manage_investment.html', {'form': form})


# user transaction list

@login_required
def dashboard_view(request):
    # Filter all transactions for the logged-in user and transactions created by the admin
    user_transactions = Transaction.objects.filter(user=request.user) | Transaction.objects.filter(user__id=request.user.id)

    # Calculate totals for approved transactions only
    approved_transactions = user_transactions.filter(status='approved')
    total_credit = approved_transactions.filter(amount_type='credit').aggregate(total=models.Sum('amount'))['total'] or 0
    total_debit = approved_transactions.filter(amount_type='debit').aggregate(total=models.Sum('amount'))['total'] or 0

    # If you want to calculate a specific metric like 'Investment', filter based on `particulars`
    total_returns = approved_transactions.filter(particulars__icontains='total_returns').aggregate(total=models.Sum('amount'))['total'] or 0

    context = {
        'transactions': user_transactions,  # All transactions for the user (including admin-created)
        'total_credit': total_credit,       # Total credit from approved transactions
        'total_debit': total_debit,         # Total debit from approved transactions
        'total_returns': total_returns,     # Total returns from approved transactions
    }
    return render(request, 'dashboard.html', context)


