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
from django.db import models
from decimal import Decimal
from django.core.paginator import Paginator
from django.db.models import Q
from django.views.decorators.cache import never_cache

from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib.auth import logout

from .forms import UserProfileUpdateForm


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

@never_cache
def login_view(request):
    if request.user.is_authenticated:  # Check if the user is already logged in
        # Redirect to the appropriate dashboard based on user type
        if request.user.is_superuser:
            return redirect('transaction_list')  # Redirect superusers
        elif request.user.username == 'developer':
            return redirect('/pineapplepie/')  # Redirect developer users
        else:
            return redirect('dashboard')  # Redirect normal users
        
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
    request.session.flush()  # Clear the session entirely
    return redirect('home')  # Redirect to login page



# Admin view to list all users
# Check if user is superuser
def superuser_required(user):
    return user.is_authenticated and user.is_superuser

@user_passes_test(superuser_required)
@never_cache
def admin_user_list(request):
    User = get_user_model()
    
    # Get the search query from the GET request
    search_query = request.GET.get('search', '')

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

        if action == 'confirm_toggle':
            user.is_approved = not user.is_approved
            user.save()
            status = "activated" if user.is_approved else "deactivated"
            messages.success(request, f"User {user.username} has been {status}.")
            return redirect('admin-user-list')  # Redirect to ensure message is shown on the same page
        elif action == 'promote':  # Promote to admin
            if not user.is_superuser:  # Avoid promoting an already superuser
                user.is_staff = True
                user.is_superuser = True
                user.save()
                messages.success(request, f"User {user.username} has been promoted to Admin.")
            else:
                messages.error(request, "User is already an Admin.")
        elif action == 'demote':  # Demote from admin
            if user.is_superuser:  # Ensure only superusers can be demoted
                user.is_staff = False
                user.is_superuser = False
                user.save()
                messages.success(request, f"User {user.username} has been demoted to a regular user.")
            else:
                messages.error(request, "User is not an Admin.")
        else:
            # Render the admin user list with the confirmation form
            return render(request, 'manage_users.html', {'users': users, 'search_query': search_query, 'confirm_user': user, 'confirm_action': action})

    return render(request, 'manage_users.html', {'users': users, 'search_query': search_query})


#  admin transaction list
# Check if the user is an admin (superuser)
from investapp.models import CustomUser  # Make sure you import the custom user model

def admin_required(user):
    return user.is_authenticated and user.is_staff

@user_passes_test(admin_required, login_url='login')
@never_cache
def transaction_list(request):
    if not request.user.is_authenticated:
        return redirect('home')
    
    # Get the search query (if any)
    search_query = request.GET.get('search', '')

    # Get all users who have at least one approved transaction
    users_with_transactions = CustomUser.objects.filter(
        transactions__status='approved'
    ).distinct()

    # Apply search filter if a search query is provided
    if search_query:
        users_with_transactions = users_with_transactions.filter(username__icontains=search_query)

    # Initialize total return amount for all users
    total_return_amount = 0

    # Collect user balances and transaction details
    user_balances = []
    for user in users_with_transactions:
        # Filter approved transactions for the user
        transactions = Transaction.objects.filter(user=user, status='approved')

        # Total credit and debit amounts
        total_credit = transactions.filter(amount_type='credit').aggregate(Sum('amount'))['amount__sum'] or 0
        total_debit = transactions.filter(amount_type='debit').aggregate(Sum('amount'))['amount__sum'] or 0

        # Initial investment: First credit transaction amount or 0
        first_transaction = transactions.filter(amount_type='credit').order_by('id').first()
        initial_value = first_transaction.amount if first_transaction else 0

        # Current value: The balance after all credits and debits
        current_value = total_credit - total_debit

        # Calculate the return amount (current value - initial invested amount)
        return_amount = current_value - initial_value if initial_value > 0 else 0
        total_return_amount += return_amount  # Accumulate total return amount for all users

        # Get the latest transaction for additional details
        latest_transaction = transactions.order_by('-date').first()

        # Add user details to the balances list
        user_balances.append({
            'username': user.username,
            'balance': current_value,
            'date': latest_transaction.date if latest_transaction else None,
            'particulars': latest_transaction.particulars if latest_transaction else "N/A",
            'narration': latest_transaction.narration if latest_transaction else "N/A",
            'amount_type': latest_transaction.amount_type if latest_transaction else "N/A",
            'amount': total_credit,  # Total credited amount
            'return_amount': return_amount,  # Return amount for this user
        })

    # Paginate the user_balances list
    paginator = Paginator(user_balances, 8)  # Show 8 users per page
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    # Calculate the starting index for this page
    start_index = paginator.per_page * (page_obj.number - 1)

    # Calculate totals for the cards (approved transactions)
    approved_transactions = Transaction.objects.filter(status='approved')
    credit_total = approved_transactions.filter(amount_type='credit').aggregate(Sum('amount'))['amount__sum'] or 0
    total_withdrawal = approved_transactions.filter(amount_type='debit').aggregate(Sum('amount'))['amount__sum'] or 0

    # Pass data to the template
    return render(request, 'transaction_list.html', {
        'user_balances': page_obj,
        'credit_total': credit_total,
        'total_withdrawal': total_withdrawal,
        'total_return_amount': total_return_amount,  # Total return amount of all users
        'search_query': search_query,
        'start_index': start_index,  # Pass the starting index
    })


# approvals and rejections and create transaction for user by admin

@login_required
@user_passes_test(lambda u: u.is_staff)  # Ensure only staff can access
@never_cache
def pending_transactions(request):
    # Get all transactions with 'pending' status
    transactions = Transaction.objects.filter(status='pending').order_by('-date')

    # Pagination
    paginator = Paginator(transactions, 4)  # Show 4 transactions per page
    page_number = request.GET.get('page')  # Get the page number from the request
    page_obj = paginator.get_page(page_number)

    # Handle form submission for new transaction
    if request.method == 'POST':
        form = TransactionForm(request.POST, request.FILES)
        if form.is_valid():
            transaction = form.save(commit=False)  # Do not save yet
            transaction.status = 'approved'  # Automatically approve the transaction
            
            # Set the user for the transaction
            user_id = request.POST.get('user')  # Get the selected user
            try:
                user = CustomUser.objects.get(id=user_id)  # Fetch the user
                transaction.user = user  # Set the user for the transaction
            except CustomUser.DoesNotExist:
                messages.error(request, "Selected user does not exist.")
                return render(request, 'pending_transactions.html', {'page_obj': page_obj, 'form': form})

            transaction.save()  # Save the transaction
            messages.success(request, "Transaction created and approved successfully.")
            return redirect('pending_transactions')  # Redirect to avoid duplicate submissions

    else:
        form = TransactionForm()  # Create an empty form for GET request

    return render(request, 'pending_transactions.html', {
        'page_obj': page_obj,
        'form': form,  # Pass the form to the template
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
@never_cache
def admin_user_home(request, user_id=None):
    # Filter users who have at least one approved transaction
    users_with_transactions = CustomUser.objects.filter(
        transactions__status='approved'
    ).distinct()

    user_data = []
    for user in users_with_transactions:
        # Filter only approved transactions for the user
        transactions = Transaction.objects.filter(user=user, status='approved')

        # Calculate total credit and total debit
        total_credit = transactions.filter(amount_type='credit').aggregate(Sum('amount'))['amount__sum'] or 0
        total_debit = transactions.filter(amount_type='debit').aggregate(Sum('amount'))['amount__sum'] or 0

        # Use total returns from the user's dashboard
        # (Fetch `dashboard_view` data dynamically or calculate here)
        dashboard_view_data = calculate_user_dashboard_returns(user)  # Reuse logic
        total_returns = dashboard_view_data['total_returns']  # Get from user dashboard

        # Append user data
        user_data.append({
            'username': user.username,
            'user_id': user.id,
            'debit_total': total_debit,
            'credit_total': total_credit,
            'total_returns': total_returns,  # Use value from the user's dashboard
            'status': 'Active' if total_returns > 0 else 'Inactive',
        })

    # Paginate the user data
    paginator = Paginator(user_data, 10)  # Show 10 users per page
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    # If user_id is provided, retrieve selected user and their ledger
    ledger_data = None
    selected_user = None
    if user_id:
        selected_user = get_object_or_404(CustomUser, id=user_id)
        ledger_data = Transaction.objects.filter(user=selected_user, status='approved')

        # Initialize balance for the selected user
        running_balance = 0
        for transaction in ledger_data:
            if transaction.amount_type == 'credit':
                running_balance += transaction.amount
            elif transaction.amount_type == 'debit':
                running_balance -= transaction.amount
            # Add the running balance to each transaction in the context
            transaction.running_balance = running_balance

    # Pass data to the template
    return render(request, 'admin-user-dashboard.html', {
        'page_obj': page_obj,
        'ledger_data': ledger_data,
        'selected_user': selected_user,
    })



# for users creating transaction view

@never_cache
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

@never_cache
@login_required
def dashboard_view(request):
    # Filter all transactions for the logged-in user and transactions created by the admin
    user_transactions = Transaction.objects.filter(user=request.user) | Transaction.objects.filter(user__id=request.user.id)

    # Order by status (pending first) and then by date (latest first)
    user_transactions = user_transactions.order_by(
        models.Case(
            models.When(status='pending', then=0),
            default=1,
            output_field=models.IntegerField()
        ),
        '-date'  # Sort by date in descending order (latest first)
    )

    # Pagination
    paginator = Paginator(user_transactions, 6)  # Show 6 transactions per page
    page_number = request.GET.get('page')  # Get the current page number from query parameters
    page_obj = paginator.get_page(page_number)  # Get the transactions for the current page

    # Use the helper function to calculate the transaction summary
    transaction_summary = calculate_user_dashboard_returns(request.user)

    context = {
        'transactions': page_obj,  # Paginated transactions
        'total_credit': transaction_summary['total_credit'],  # Total credit from approved transactions
        'total_debit': transaction_summary['total_debit'],    # Total debit from approved transactions
        'total_returns': transaction_summary['total_returns'],  # Total returns as a percentage
        'start_index': (page_obj.number - 1) * page_obj.paginator.per_page  # Add this to calculate serial number
    }

    return render(request, 'dashboard.html', context)



# common calculation for both user and admin side
def calculate_user_dashboard_returns(user):
    transactions = Transaction.objects.filter(user=user, status='approved')
    total_credit = transactions.filter(amount_type='credit').aggregate(Sum('amount'))['amount__sum'] or 0
    total_debit = transactions.filter(amount_type='debit').aggregate(Sum('amount'))['amount__sum'] or 0

    first_credit_transaction = transactions.filter(amount_type='credit').order_by('id').first()
    initial_value = first_credit_transaction.amount if first_credit_transaction else 0
    current_value = total_credit - total_debit

    if initial_value > 0:
        total_returns = round(((current_value - initial_value) / initial_value) * 100, 2)
    else:
        total_returns = 0

    return {
        'total_returns': total_returns,
        'total_credit': total_credit,
        'total_debit': total_debit,
        'initial_value': initial_value,
        'current_value': current_value,
    }


# update profile for users
@never_cache
@login_required
def update_profile(request):
    user = request.user

    if request.method == 'POST':
        form = UserProfileUpdateForm(request.POST, instance=user)

        if form.is_valid():
            # Check if the password field is changed
            password_changed = bool(form.cleaned_data.get('password'))

            # Save the form
            form.save()

            # Redirect to login only if the password was changed
            if password_changed:
                logout(request)  # Log the user out
                return redirect('login')  # Redirect to login page

            # Redirect to the dashboard if no password was changed
            return redirect('dashboard')  # Redirect prevents the form from resubmitting
    else:
        form = UserProfileUpdateForm(instance=user)

    return render(request, 'update_profile.html', {'form': form})


# for admins profile update form
# Decorator to ensure only admins can access this view
def admin_only(user):
    return user.is_staff or user.is_superuser

@never_cache
@user_passes_test(admin_only)
def admin_update_profile(request):
    admin_user = request.user

    if request.method == 'POST':
        form = UserProfileUpdateForm(request.POST, instance=admin_user)

        if form.is_valid():
            # Save the admin profile
            form.save()

            # Redirect back to the admin dashboard
            return redirect('transaction_list')  # Adjust the name of the admin dashboard URL
        else:
            messages.error(request, "Please correct the errors below.")
    else:
        form = UserProfileUpdateForm(instance=admin_user)

    return render(request, 'updateprofile.html', {'form': form})
