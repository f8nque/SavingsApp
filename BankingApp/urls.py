# urls.py
from django.urls import path
from . import views

app_name = 'BankingApp'

urlpatterns = [
    path('', views.DashboardView.as_view(), name='dashboard'),
    path('banks/', views.BankListView.as_view(), name='bank_list'),
    path('banks/<int:bank_id>/', views.BankDetailView.as_view(), name='bank_detail'),
]
