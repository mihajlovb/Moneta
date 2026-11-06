from django.urls import path, reverse_lazy
from django.contrib.auth import views as auth_views
from . import views

app_name = 'finance'

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('transactions/', views.transaction_list, name='transactions'),
    path('transactions/add/', views.transaction_add, name='transaction_add'),
    path('transactions/<int:pk>/edit/', views.transaction_edit, name='transaction_edit'),
    path('transactions/<int:pk>/delete/', views.transaction_delete, name='transaction_delete'),
    path('accounts/', views.account_list, name='accounts'),
    path('accounts/add/', views.account_add, name='account_add'),
    path('accounts/<int:pk>/edit/', views.account_edit, name='account_edit'),
    path('budgets/', views.budget_list, name='budgets'),
    path('budgets/add/', views.budget_add, name='budget_add'),
    path('budgets/<int:pk>/edit/', views.budget_edit, name='budget_edit'),
    path('budgets/<int:pk>/delete/', views.budget_delete, name='budget_delete'),
    path('goals/', views.goal_list, name='goals'),
    path('goals/add/', views.goal_add, name='goal_add'),
    path('goals/<int:pk>/edit/', views.goal_edit, name='goal_edit'),
    path('goals/<int:pk>/delete/', views.goal_delete, name='goal_delete'),
    path('markets/', views.markets, name='markets'),
    path('markets/data/', views.market_data, name='market_data'),
    path('recurring/', views.recurring, name='recurring'),
    path('reports/', views.reports, name='reports'),
    path('settings/', views.user_settings, name='settings'),
    path('settings/password/', auth_views.PasswordChangeView.as_view(
        template_name='registration/password_change_form.html',
        success_url=reverse_lazy('finance:settings'),
    ), name='password_change'),
]
