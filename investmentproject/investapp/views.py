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
from .forms import CustomUserCreationForm
from django.core.paginator import Paginator
from django.db.models import Q


# home page
def home(request):
    return render(request, 'home.html')


# signup form

def signup_view(request):
    if request.method == 'POST':
        form = SignupForm(request.POST)
        if form.is_valid():
            user = form.save(commit=False)
            user.is_approved = False  # New users will not be approved automatically
            user.save()

            # Add a success message
            messages.success(request, "Your account has been created. Please wait for approval.")
            return render(request, 'signup.html', {'form': form})  # Re-render signup page with the success message
    else:
        form = SignupForm()

    return render(request, 'signup.html', {'form': form})



# login for all

def login_view(request):
    if request.method == 'POST':
        username_or_email = request.POST['username']  # Field for username or email
        password = request.POST['password']
        
        # Try to authenticate using the username or email
        user = None
        if '@' in username_or_email:  # If the input looks like an email
            try:
                user = CustomUser.objects.get(email=username_or_email)  # Get user by email (CustomUser model)
            except CustomUser.DoesNotExist:
                user = None
        else:
            user = authenticate(request, username=username_or_email, password=password)  # Authenticate by username
        
        if user is not None and user.check_password(password):
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
    
    # Get the search query from the GET request
    search_query = request.GET.get('search', '')  # Default to empty string if no search query

    # Filter users based on the search query (first name or last name contains the search term)
    if search_query:
        users = User.objects.exclude(username='developer').filter(
            first_name__icontains=search_query
        ) | User.objects.exclude(username='developer').filter(
            last_name__icontains=search_query
        )
    else:
        users = User.objects.exclude(username='developer')  # If no search query, show all users

    if request.method == 'POST':
        user_id = request.POST.get('user_id')
        action = request.POST.get('action')

        try:
            user = User.objects.get(id=user_id)
        except User.DoesNotExist:
            messages.error(request, "User not found.")
            return redirect('admin-user-list')

        # Toggle the approval status
        if action == 'toggle':
            user.is_approved = not user.is_approved  # Toggle the status
        else:
            messages.error(request, "Invalid action.")
            return redirect('admin-user-list')

        user.save()
        status = "activated" if user.is_approved else "deactivated"
        messages.success(request, f"User {user.username} has been {status}.")

    return render(request, 'manage_users.html', {'users': users, 'search_query': search_query})



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
                return render(request, 'create_transaction.html', {'form': form})

            transaction.save()  # Save the transaction
            messages.success(request, "Transaction created and approved successfully.")
            
            # Do not redirect here, just render the page with the message
            return render(request, 'create_transaction.html', {'form': TransactionForm()})

    else:
        form = TransactionForm()

    return render(request, 'create_transaction.html', {'form': form})


#  admin transaction list
# Check if the user is an admin (superuser)
from investapp.models import CustomUser  # Make sure you import the custom user model

def admin_required(user):
    return user.is_authenticated and user.is_staff

@user_passes_test(admin_required, login_url='login')

def transaction_list(request):
    # Get the search query (if any)
    search_query = request.GET.get('search', '')

    # Get all users who have made transactions
    users_with_transactions = Transaction.objects.values('user').distinct()

    # Filter users by the search query
    if search_query:
        users_with_transactions = users_with_transactions.filter(user__username__icontains=search_query)

    # Initialize total return amount
    total_return_amount = 0

    # Collect user balances and transaction details
    user_balances = []
    for user_data in users_with_transactions:
        user = CustomUser.objects.get(id=user_data['user'])  # Get the user instance
        transactions = Transaction.objects.filter(user=user, status='approved')

        # Calculate totals and balance
        total_credit = transactions.filter(amount_type='credit').aggregate(Sum('amount'))['amount__sum'] or 0
        total_debit = transactions.filter(amount_type='debit').aggregate(Sum('amount'))['amount__sum'] or 0
        balance = total_credit - total_debit

        # Total amount invested (sum of all credit transactions)
        total_invested = total_credit  # Sum of all credit transactions

        # Calculate the return percentage for the user
        if total_invested > 0:
            user_return_percentage = round(((balance - total_invested) / total_invested) * 100, 2)
        else:
            user_return_percentage = 0  # Avoid division by zero

        # Add the user's return percentage to the total return amount
        total_return_amount += user_return_percentage

        # Get the latest transaction for additional details
        latest_transaction = transactions.order_by('-date').first()

        # Add user details with transaction fields
        user_balances.append({
            'username': user.username,
            'balance': balance,
            'date': latest_transaction.date if latest_transaction else None,
            'particulars': latest_transaction.particulars if latest_transaction else "N/A",
            'narration': latest_transaction.narration if latest_transaction else "N/A",
            'amount_type': latest_transaction.amount_type if latest_transaction else "N/A",
            'amount': total_invested,  # This is now the total invested amount
            'return_percentage': user_return_percentage,
        })


    # Calculate totals for the cards
    approved_transactions = Transaction.objects.filter(status='approved')
    credit_total = approved_transactions.filter(amount_type='credit').aggregate(Sum('amount'))['amount__sum'] or 0
    total_withdrawal = approved_transactions.filter(amount_type='debit').aggregate(Sum('amount'))['amount__sum'] or 0

    # Pass data to the template
    return render(request, 'transaction_list.html', {
        'user_balances': user_balances,
        'credit_total': credit_total,
        'total_withdrawal': total_withdrawal,
        'total_return_amount': total_return_amount,
        'search_query': search_query,
    })


@login_required
@user_passes_test(lambda user: user.is_staff)
def pending_transactions(request):
    # Get all transactions with 'pending' status
    transactions = Transaction.objects.filter(status='pending').order_by('-date')

    # Pagination
    paginator = Paginator(transactions, 4)  # Show 10 transactions per page
    page_number = request.GET.get('page')  # Get the page number from the request
    page_obj = paginator.get_page(page_number)

    return render(request, 'pending_transactions.html', {
        'page_obj': page_obj,
    })

@login_required
@user_passes_test(lambda user: user.is_staff)
def approve_transaction(request, transaction_id):
    if request.method == 'POST':
        transaction = get_object_or_404(Transaction, id=transaction_id)
        transaction.status = 'approved'
        transaction.save()
        return redirect('pending_transactions')

@login_required
@user_passes_test(lambda user: user.is_staff)
def reject_transaction(request, transaction_id):
    if request.method == 'POST':
        transaction = get_object_or_404(Transaction, id=transaction_id)
        transaction.status = 'rejected'
        transaction.save()
        return redirect('pending_transactions')


# admin user dahsboard
def decimal_to_float(value):
    if isinstance(value, Decimal):
        return float(value)
    return value

@login_required
@user_passes_test(lambda user: user.is_staff)
def admin_user_home(request, user_id=None):
    # Filter users who have at least one approved transaction
    users_with_transactions = CustomUser.objects.filter(
        is_staff=False, 
        is_superuser=False,
        transactions__status='approved'  # Filter for approved transactions
    ).distinct()  # Ensure no duplicates due to joins

    user_data = []
    for user in users_with_transactions:
        # Filter only approved transactions for the user
        transactions = Transaction.objects.filter(user=user, status='approved')
        total_credit = transactions.filter(amount_type='credit').aggregate(Sum('amount'))['amount__sum'] or 0
        total_debit = transactions.filter(amount_type='debit').aggregate(Sum('amount'))['amount__sum'] or 0

        # Calculate initial and current values
        first_transaction = transactions.filter(amount_type='credit').order_by('id').first()
        initial_value = first_transaction.amount if first_transaction else 0
        current_value = total_credit - total_debit

        # Calculate returns percentage
        if initial_value > 0:
            total_returns = round(((current_value - initial_value) / initial_value) * 100, 2)
        else:
            total_returns = 0  # Avoid division by zero

        # Append user data with calculated returns
        user_data.append({
            'username': user.username,                    
            'user_id': user.id,
            'debit_total': total_debit,
            'credit_total': total_credit,
            'total_returns': total_returns,  # Total returns as a percentage
            'status': 'Active' if total_returns > 0 else 'Inactive',
        })

    # If user_id is provided, retrieve selected user and their ledger
    ledger_data = None
    selected_user = None
    if user_id:
        selected_user = get_object_or_404(CustomUser, id=user_id)
        ledger_data = Transaction.objects.filter(user=selected_user, status='approved').order_by('-date')

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

    # Pagination
    paginator = Paginator(user_transactions, 6)  # Show 6 transactions per page
    page_number = request.GET.get('page')  # Get the current page number from query parameters
    page_obj = paginator.get_page(page_number)  # Get the transactions for the current page

    # Calculate totals for approved transactions only
    approved_transactions = user_transactions.filter(status='approved')

    # Total credit and debit amounts
    total_credit = approved_transactions.filter(amount_type='credit').aggregate(total=models.Sum('amount'))['total'] or 0
    total_debit = approved_transactions.filter(amount_type='debit').aggregate(total=models.Sum('amount'))['total'] or 0

    # Calculate initial and current values
    initial_value = approved_transactions.filter(amount_type='credit', status='approved').first().amount if approved_transactions.exists() else 0
    current_value = total_credit - total_debit

    # Calculate returns percentage
    if initial_value > 0:
        total_returns = round(((current_value - initial_value) / initial_value) * 100, 2)

    else:
        total_returns = 0  # Avoid division by zero

    context = {
        'transactions': page_obj,  # Paginated transactions
        'total_credit': total_credit,  # Total credit from approved transactions
        'total_debit': total_debit,    # Total debit from approved transactions
        'total_returns': total_returns,  # Total returns as a percentage
        'start_index': (page_obj.number - 1) * page_obj.paginator.per_page  # Add this to calculate serial number
    }
    return render(request, 'dashboard.html', context)



# .............................
# views for admin to creae user 

@login_required
@user_passes_test(lambda u: u.is_staff)
def create_user(request):
    if request.method == 'POST':
        form = CustomUserCreationForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'User created successfully!')
            return redirect('admin-user-list')  # Redirect to user list or any other relevant page
    else:
        form = CustomUserCreationForm()

    return render(request, 'create_user.html', {'form': form})
