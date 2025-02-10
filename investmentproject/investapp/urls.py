# urls.py
from django.urls import path
from . import views
# from .views import user_transaction_detail

from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('signup/', views.signup_view, name='signup'),
    path('login/', views.login_view, name='login'),
    path('dashboard/', views.dashboard_view, name='dashboard'),
    path('logout/', views.logout_view, name='logout'),
    path('admin/user-list/', views.admin_user_list, name='admin-user-list'),
    path('transactions/', views.transaction_list, name='transaction_list'),
    path('manage_investment/', views.manage_investment, name='manage_investment'),
    path('admin_home/', views.admin_user_home, name='admin_user_home'),
    path('pending-transactions/', views.pending_transactions, name='pending_transactions'),
    path('approve-transaction/<int:transaction_id>/', views.approve_transaction, name='approve_transaction'),
    path('reject-transaction/<int:transaction_id>/', views.reject_transaction, name='reject_transaction'),
    path('user_ledger/<int:user_id>/', views.admin_user_home, name='user_ledger'),
    path('pendingapproval', views.pendingapproval, name='pendingapproval'),
    path('get-all-users/', views.get_all_users, name='get_all_users'),
    path('export-transactions/',views.export_transactions_pdf, name='export_transactions'),
path('admin/users/download/pdf/',views.download_users_pdf, name='download-users-pdf'),
    path('admin/users/download/excel/',views.download_users_excel, name='download-users-excel'),


    path('projects/', views.project_list, name='project_list'),
     path('projects/create/', views.project_create, name='project_create'),
    path('projects/edit/<int:pk>/', views.project_edit, name='project_edit'),   
     path('projects/delete/<int:pk>/', views.project_delete, name='project_delete'), 



    path('documents/', views.document_list, name='document_list'),
    path('documents/upload/', views.upload_document, name='upload_document'),
    path('documents/edit/<int:document_id>/', views.edit_document, name='edit_document'),
    path('documents/delete/<int:document_id>/',views.delete_document, name='delete_document'),


# 
 path('admin/users/<int:user_id>/documents/', views.admin_user_documents, name='admin_user_documents'),
    path('admin/users/documents/delete/<int:document_id>/', views.admin_delete_document, name='admin_delete_document'),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

