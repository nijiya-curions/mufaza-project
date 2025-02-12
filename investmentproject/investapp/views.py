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
from django.http import HttpResponse
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors


from .models import InvestmentProject, UserProjectAssignment, CustomUser,UserDocument
from .forms import UserProjectAssignmentForm,UserDocumentForm



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
            # Redirect to the pending approval page
            return redirect('pendingapproval')
    else:
        form = SignupForm()

    return render(request, 'signup.html', {'form': form})



# login for all

@never_cache
def login_view(request):
    if request.user.is_authenticated:  # Check if user is already logged in
        # Redirect based on user type
        if request.user.is_superuser:
            return redirect('/pineapplepie/')  # Redirect superusers to Django admin
        elif request.user.is_staff:
            return redirect('transaction_list')  # Redirect staff to admin dashboard
        else:
            return redirect('dashboard')  # Redirect normal users to user dashboard
        
    if request.method == 'POST':
        username_or_email = request.POST['username']
        password = request.POST['password']
        
        # Try to authenticate using username or email
        user = None
        if '@' in username_or_email:
            try:
                user = CustomUser.objects.get(email=username_or_email)
            except CustomUser.DoesNotExist:
                user = None
        else:
            user = authenticate(request, username=username_or_email, password=password)
        
        if user is not None and user.check_password(password):
            if not user.is_approved and not (user.is_superuser or user.is_staff):
                return render(request, 'pending_approval.html', 
                    {'error': 'Your account is awaiting approval by an administrator.'})
            
            login(request, user)
            
            # Redirect based on user type
            if user.is_superuser:
                return redirect('/pineapplepie/')  # Django admin dashboard
            elif user.is_staff:
                return redirect('transaction_list')  # Admin dashboard
            else:
                return redirect('dashboard')  # User dashboard
            
        else:
            return render(request, 'login.html', {'error': 'Invalid credentials'})
    
    return render(request, 'login.html')


# logout

def logout_view(request):
    logout(request)
    request.session.flush()  # Clear the session entirely
    return redirect('home')  # Redirect to login page


# Admin view to list all users
def admin_required(user):
    return user.is_authenticated and user.is_staff

@user_passes_test(admin_required, login_url='home')
@never_cache
def admin_user_list(request):
    User = get_user_model()

    # Get the search query from the GET request
    search_query = request.GET.get('search', '')

    # Filter users based on the search query
    if search_query:
        users = User.objects.exclude(is_superuser=True).filter(
            first_name__icontains=search_query
        ) | User.objects.exclude(is_superuser=True).filter(
            last_name__icontains=search_query
        )
    else:
        users = User.objects.exclude(is_superuser=True)

    # Sort users: Show not activated (is_approved=False) first, then activated users
    users = users.order_by('is_approved', 'first_name')

    # Pagination: Show 10 users per page
    paginator = Paginator(users, 10)
    page_number = request.GET.get('page')
    page_users = paginator.get_page(page_number)

    if request.method == 'POST':
        user_id = request.POST.get('user_id')
        action = request.POST.get('action')

        try:
            user = User.objects.get(id=user_id)
        except User.DoesNotExist:
            messages.error(request, "User not found.")
            return redirect('admin-user-list')

        # Only staff users can promote/demote other users
        if request.user.is_staff:
            if action == 'confirm_toggle':
                user.is_approved = not user.is_approved
                user.save()
                status = "activated" if user.is_approved else "deactivated"
                messages.success(request, f"User {user.username} has been {status}.")
                return redirect('admin-user-list')
            elif action == 'promote':  # Promote to staff
                if not user.is_staff:
                    user.is_staff = True
                    user.save()
                    messages.success(request, f"User {user.username} has been promoted to Staff.")
                else:
                    messages.error(request, "User is already a Staff member.")
            elif action == 'demote':  # Demote from staff
                if user.is_staff:
                    user.is_staff = False
                    user.save()
                    messages.success(request, f"User {user.username} has been demoted to a regular user.")
                else:
                    messages.error(request, "User is not a Staff member.")
        else:
            messages.error(request, "You do not have permission to perform this action.")
            return redirect('admin-user-list')

    return render(request, 'manage_users.html', {
        'users': page_users,  # Paginated users
        'search_query': search_query
    })



#  admin transaction list
# Check if the user is an admin (superuser)
from investapp.models import CustomUser  # Make sure you import the custom user model

def admin_required(user):
    return user.is_authenticated and user.is_staff

@user_passes_test(admin_required, login_url='home')
@never_cache
def transaction_list(request):
    # Redirect superusers to Django admin
    if request.user.is_superuser:
        return redirect('/pineapplepie/')
    elif not request.user.is_staff:
        return redirect('dashboard')

    # Handle Profile Update Form Submission
    if request.method == "POST" and "update_profile" in request.POST:
        form = UserProfileUpdateForm(request.POST, instance=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, "Profile updated successfully!")
            return redirect('transaction_list')  # Stay on the same page
        else:
            messages.error(request, "Please correct the errors below.")
    else:
        form = UserProfileUpdateForm(instance=request.user)

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
        'form': form,  # Pass the form to the template
    })



# approvals and rejections and create transaction for user by admin

def admin_required(user):
    return user.is_authenticated and user.is_staff

@user_passes_test(admin_required, login_url='home')
@never_cache
def pending_transactions(request):
    # Get the sort filter from the request
    sort_option = request.GET.get('sort', '')  # 'credit', 'debit'

    # Filter transactions by 'pending' status
    transactions = Transaction.objects.filter(status='pending')

    # Apply sorting based on the `amount_type`
    if sort_option == 'credit':
        transactions = transactions.filter(amount_type='credit')
    elif sort_option == 'debit':
        transactions = transactions.filter(amount_type='debit')

    # Order transactions by date (most recent first)
    transactions = transactions.order_by('-date')

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
        # Exclude superusers from the user field's queryset
        form.fields['user'].queryset = CustomUser.objects.filter(is_superuser=False)

    return render(request, 'pending_transactions.html', {
        'page_obj': page_obj,
        'form': form,  # Pass the form to the template
        'sort_option': sort_option,  # Pass the current sort option to the template
    })


def admin_required(user):
    return user.is_authenticated and user.is_staff

@user_passes_test(admin_required, login_url='home')
@never_cache
def approve_transaction(request, transaction_id):
    if request.method == 'POST':
        transaction = get_object_or_404(Transaction, id=transaction_id)
        transaction.status = 'approved'
        transaction.save()
        return redirect('pending_transactions')


def admin_required(user):
    return user.is_authenticated and user.is_staff

@user_passes_test(admin_required, login_url='login')
@never_cache
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


def admin_required(user):
    return user.is_authenticated and user.is_staff

@user_passes_test(admin_required, login_url='home')
@never_cache
def admin_user_home(request, user_id=None):
    # Get the search query from the request
    search_query = request.GET.get('search', '')

    # Filter users who have at least one approved transaction
    users_with_transactions = CustomUser.objects.filter(
        transactions__status='approved'
    ).distinct()

    # Apply search filter if a search query is provided
    if search_query:
        users_with_transactions = users_with_transactions.filter(
            Q(username__icontains=search_query) |
            Q(email__icontains=search_query)
        )

    user_data = []
    for user in users_with_transactions:
        # Filter only approved transactions for the user
        transactions = Transaction.objects.filter(user=user, status='approved')

        # Calculate total credit and total debit
        total_credit = transactions.filter(amount_type='credit').aggregate(Sum('amount'))['amount__sum'] or 0
        total_debit = transactions.filter(amount_type='debit').aggregate(Sum('amount'))['amount__sum'] or 0

        # Use total returns from the user's dashboard
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
    paginator = Paginator(user_data, 7)  # Show 7 users per page
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
        'search_query': search_query,  # Pass the search query to the template
    })


# for users creating transaction view

def user_required(user):
    return user.is_authenticated and not user.is_staff  # Ensures only non-admin users can access

user_login_required = user_passes_test(user_required, login_url='home')



@never_cache
@user_login_required
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
@user_login_required
def dashboard_view(request):
     # Redirect users based on their role
    if request.user.is_superuser:
        return redirect('/pineapplepie/')
    elif request.user.is_staff:
        return redirect('transaction_list')
    # Handle profile update form submission
    user = request.user
    if request.method == 'POST' and 'update_profile' in request.POST:
        form = UserProfileUpdateForm(request.POST, instance=user)
        if form.is_valid():
            password_changed = bool(form.cleaned_data.get('password'))
            form.save()

            if password_changed:
                logout(request)  # Log out the user if they change the password
                return redirect('login')

            return redirect('dashboard')  # Stay on the dashboard after update
    else:
        form = UserProfileUpdateForm(instance=user)


    # Fetch transactions
    pending_transactions = Transaction.objects.filter(user=request.user, status='pending')
    approved_rejected_transactions = Transaction.objects.filter(user=request.user).exclude(status='pending').order_by('date')

    running_balance = 0
    for transaction in approved_rejected_transactions:
        if transaction.amount_type == 'credit':
            running_balance += transaction.amount
        elif transaction.amount_type == 'debit':
            running_balance -= transaction.amount
        transaction.running_balance = running_balance

    # Pagination
    pending_paginator = Paginator(pending_transactions, 6)
    pending_page_obj = pending_paginator.get_page(request.GET.get('pending_page'))
    approved_rejected_paginator = Paginator(approved_rejected_transactions, 6)
    approved_rejected_page_obj = approved_rejected_paginator.get_page(request.GET.get('approved_rejected_page'))

    transaction_summary = calculate_user_dashboard_returns(request.user)

    context = {
        'pending_transactions': pending_page_obj,
        'approved_rejected_transactions': approved_rejected_page_obj,
        'total_credit': transaction_summary['total_credit'],
        'total_debit': transaction_summary['total_debit'],
        'total_returns': transaction_summary['total_returns'],
        'pending_start_index': (pending_page_obj.number - 1) * pending_page_obj.paginator.per_page,
        'approved_rejected_start_index': (approved_rejected_page_obj.number - 1) * approved_rejected_page_obj.paginator.per_page,
        'all_approved_rejected_transactions': approved_rejected_transactions,
        'form': form  # Add the form to the context
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



# pending approval
def pendingapproval(request):
    return render(request,'pending_approval.html')


# for downloading all user transaction details by admin
from django.http import JsonResponse

def get_all_users(request):
    users_with_transactions = CustomUser.objects.filter(
        transactions__status='approved'
    ).distinct()

    user_data = []
    for user in users_with_transactions:
        transactions = Transaction.objects.filter(user=user, status='approved')

        total_credit = transactions.filter(amount_type='credit').aggregate(Sum('amount'))['amount__sum'] or 0
        total_debit = transactions.filter(amount_type='debit').aggregate(Sum('amount'))['amount__sum'] or 0

        dashboard_view_data = calculate_user_dashboard_returns(user)
        total_returns = dashboard_view_data['total_returns']

        user_data.append({
            'user_id': user.id,
            'username': user.username,
            'credit_total': total_credit,
            'total_returns': total_returns,
            'status': 'Active' if total_returns > 0 else 'Inactive',
        })

    return JsonResponse({'users': user_data})


# for user dashboard download pdf
def export_transactions_pdf(request):
    user = request.user
    transactions = Transaction.objects.filter(user=user).exclude(status='pending').order_by('date')

    # Create a PDF response
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = 'attachment; filename="transactions.pdf"'

    # Create PDF object
    pdf = canvas.Canvas(response, pagesize=letter)
    pdf.setTitle("Transaction Report")

    # Set starting position
    y_position = 750  # Adjust Y position for each row
    pdf.setFont("Helvetica-Bold", 16)
    pdf.drawString(200, y_position, "Transaction Report")  
    y_position -= 30

    # Column Titles
    pdf.setFont("Helvetica-Bold", 10)
    pdf.drawString(50, y_position, "Date")
    pdf.drawString(150, y_position, "Particulars")
    pdf.drawString(300, y_position, "Amount Type")
    pdf.drawString(400, y_position, "Amount")
    pdf.drawString(500, y_position, "Status")
    y_position -= 20

    # Draw a line
    pdf.setStrokeColor(colors.black)
    pdf.line(50, y_position, 550, y_position)
    y_position -= 15

    # Transaction Data
    pdf.setFont("Helvetica", 10)
    for transaction in transactions:
        if y_position < 50:  # Start new page if needed
            pdf.showPage()
            y_position = 750  # Reset position

        pdf.drawString(50, y_position, str(transaction.date))
        pdf.drawString(150, y_position, transaction.particulars[:20])  # Truncate for space
        pdf.drawString(300, y_position, transaction.amount_type.capitalize())
        pdf.drawString(400, y_position, str(transaction.amount))
        pdf.drawString(500, y_position, transaction.status.capitalize())
        y_position -= 20  # Move down

    pdf.save()
    return response


# to download data on manage_user page by admin
from django.http import HttpResponse
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from io import BytesIO

def download_users_pdf(request):
    User = get_user_model()
    users = User.objects.exclude(is_superuser=True)

    # Create a PDF response
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = 'attachment; filename="user_list.pdf"'

    buffer = BytesIO()
    p = canvas.Canvas(buffer, pagesize=letter)
    width, height = letter

    # Title
    p.setFont("Helvetica-Bold", 16)
    p.drawString(200, height - 50, "User List")

    # Table Header
    p.setFont("Helvetica-Bold", 12)
    p.drawString(50, height - 80, "ID")
    p.drawString(100, height - 80, "Username")
    p.drawString(200, height - 80, "First Name")
    p.drawString(300, height - 80, "Last Name")
    p.drawString(400, height - 80, "Phone Number")
    p.drawString(500, height - 80, "Email")
    p.drawString(600, height - 80, "Is Staff")

    # Table Data
    y = height - 100
    p.setFont("Helvetica", 10)
    for user in users:
        p.drawString(50, y, str(user.id))
        p.drawString(100, y, user.username)
        p.drawString(200, y, user.first_name or "-")
        p.drawString(300, y, user.last_name or "-")
        p.drawString(400, y, user.phone_number or "-")
        p.drawString(500, y, user.email or "-")
        p.drawString(600, y, "Yes" if user.is_staff else "No")
        y -= 20

    p.save()
    pdf = buffer.getvalue()
    buffer.close()
    response.write(pdf)
    return response


import openpyxl
from django.http import HttpResponse

def download_users_excel(request):
    User = get_user_model()
    users = User.objects.exclude(is_superuser=True)

    # Create an Excel workbook and sheet
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Users"

    # Add headers
    headers = ["ID", "Username", "First Name", "Last Name","Phone Number","Email", "Is Staff"]
    ws.append(headers)

    # Add user data
    for user in users:
        ws.append([
            user.id,
            user.username,
            user.first_name or "-",
            user.last_name or "-",
            user.phone_number or "-",
            user.email or "-",
            "Yes" if user.is_staff else "No"
        ])

    # Create response
    response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    response['Content-Disposition'] = 'attachment; filename="user_list.xlsx"'
    wb.save(response)
    return response




# project view


from .models import InvestmentProject
from .forms import InvestmentProjectForm


# Display the list of projects
def admin_required(user):
    return user.is_authenticated and user.is_staff

@user_passes_test(admin_required, login_url='home')
@never_cache
def project_list(request):
    projects = InvestmentProject.objects.all()  # Show only user's projects
    return render(request, 'projects_list.html', {'projects': projects})

# Create a new project
def admin_required(user):
    return user.is_authenticated and user.is_staff

@user_passes_test(admin_required, login_url='home')
@never_cache
def project_create(request):
    if request.method == 'POST':
        form = InvestmentProjectForm(request.POST)
        if form.is_valid():
            form.save()  # Save project without assigning a user
            return redirect('project_list')
    else:
        form = InvestmentProjectForm()

    return render(request, 'project_create.html', {'form': form})



# Edit an existing project
def admin_required(user):
    return user.is_authenticated and user.is_staff

@user_passes_test(admin_required, login_url='home')
@never_cache
def project_edit(request, pk):
    project = get_object_or_404(InvestmentProject, pk=pk)

    if request.method == 'POST':
        form = InvestmentProjectForm(request.POST, instance=project)
        if form.is_valid():
            print("Form is valid. Saving project...")  # Debugging
            form.save()
            return redirect('project_list')
        else:
            print("Form errors:", form.errors)  # Debugging
    else:
        form = InvestmentProjectForm(instance=project)

    return render(request, 'project_edit.html', {'form': form, 'project': project})


# Delete a project
def admin_required(user):
    return user.is_authenticated and user.is_staff

@user_passes_test(admin_required, login_url='home')
@never_cache
def project_delete(request, pk):
    project = get_object_or_404(InvestmentProject, pk=pk)
    
    if request.method == 'POST':
        project.delete()
        return redirect('project_list')

    return redirect('project_list')



# assigning project for user

def admin_required(user):
    return user.is_authenticated and user.is_staff

@user_passes_test(admin_required, login_url='home')
@never_cache
def manage_project_assignments(request, user_id):
    user = get_object_or_404(CustomUser, id=user_id)  # Get the selected user
    assignments = UserProjectAssignment.objects.filter(user=user)  # Get user's assignments
    form = UserProjectAssignmentForm(initial={'user': user})  # Pre-fill user

    if request.method == "POST":
        form = UserProjectAssignmentForm(request.POST)
        if form.is_valid():
            assignment = form.save(commit=False)
            assignment.user = user  # Ensure the user is set
            assignment.save()
            return redirect('manage_project_assignments', user_id=user.id)  # Redirect with user_id

    return render(request, 'manage_projects.html', {
        'assignments': assignments,
        'form': form,
        'user': user
    })

def admin_required(user):
    return user.is_authenticated and user.is_staff

@user_passes_test(admin_required, login_url='home')
@never_cache
def edit_assignment(request, assignment_id):
    assignment = get_object_or_404(UserProjectAssignment, id=assignment_id)
    user_id = assignment.user.id  # Get the user ID

    if request.method == "POST":
        form = UserProjectAssignmentForm(request.POST, instance=assignment)
        if form.is_valid():
            form.save()
            return redirect('manage_project_assignments', user_id=user_id)  # Redirect to correct user

    else:
        form = UserProjectAssignmentForm(instance=assignment)

    return render(request, 'edit_assignment.html', {'form': form, 'user_id': user_id})


def admin_required(user):
    return user.is_authenticated and user.is_staff

@user_passes_test(admin_required, login_url='home')
@never_cache
def delete_assignment(request, assignment_id):
    assignment = get_object_or_404(UserProjectAssignment, id=assignment_id)
    user_id = assignment.user.id  # Get user ID before deleting
    assignment.delete()
    return redirect('manage_project_assignments', user_id=user_id)  # Redirect to correct user



# document section for users


@user_login_required
def document_list(request):
    """List all documents and handle document uploads and edits in the same view."""
    documents = UserDocument.objects.filter(user=request.user)
    form = UserDocumentForm()
    edit_form = None
    document_to_edit = None

    if request.method == 'POST':
        # Check if it's an edit request
        document_id = request.POST.get('edit_document_id')

        if document_id:
            document_to_edit = get_object_or_404(UserDocument, id=document_id, user=request.user)
            edit_form = UserDocumentForm(request.POST, request.FILES, instance=document_to_edit)

            if edit_form.is_valid():
                edit_form.save()
                return redirect('document_list')  # Redirect after edit

        else:
            # This is a new document upload
            form = UserDocumentForm(request.POST, request.FILES)
            if form.is_valid():
                document = form.save(commit=False)
                document.user = request.user
                document.save()
                return redirect('document_list')  # Redirect after upload

    # Handle edit request (GET request for edit form)
    document_id = request.GET.get('edit')
    if document_id:
        document_to_edit = get_object_or_404(UserDocument, id=document_id, user=request.user)
        edit_form = UserDocumentForm(instance=document_to_edit)

    return render(request, 'document_list.html', {
        'documents': documents,
        'form': form,
        'edit_form': edit_form,
        'document_to_edit': document_to_edit
    })


@user_login_required
def delete_document(request, document_id):
    """Allow users to delete their uploaded documents."""
    document = get_object_or_404(UserDocument, id=document_id, user=request.user)
    document.file.delete()  # Delete the actual file from storage
    document.delete()
    return redirect('document_list')



# document for admin side


def admin_required(user):
    return user.is_authenticated and user.is_staff

@user_passes_test(admin_required, login_url='home')
@never_cache
def admin_user_documents(request, user_id):
    User = get_user_model()
    """Admin can view and download documents uploaded by a user."""
    user = get_object_or_404(User, id=user_id)
    documents = UserDocument.objects.filter(user=user)

    return render(request, 'admin_user_documents.html', {'user': user, 'documents': documents})

def admin_required(user):
    return user.is_authenticated and user.is_staff

@user_passes_test(admin_required, login_url='home')
@never_cache
def admin_delete_document(request, document_id):
    """Admin can delete a user's document."""
    document = get_object_or_404(UserDocument, id=document_id)
    document.file.delete()  # Deletes the file from storage
    document.delete()
    messages.success(request, "Document deleted successfully.")
    return redirect('admin_user_documents', user_id=document.user.id)
