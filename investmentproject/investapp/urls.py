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
      path('transactions/create/', views.create_transaction, name='create_transaction'),
    path('transactions/', views.transaction_list, name='transaction_list'),
    path('manage_investment/', views.manage_investment, name='manage_investment'),
     path('admin_home/', views.admin_user_home, name='admin_user_home'),
  path('approve_transaction/<int:transaction_id>/', views.approve_transaction, name='approve_transaction'),
    path('reject_transaction/<int:transaction_id>/', views.reject_transaction, name='reject_transaction'),

] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

