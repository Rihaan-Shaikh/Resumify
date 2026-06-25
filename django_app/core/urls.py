"""
URL configuration for core project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/6.0/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include
from django.http import HttpResponse
from users.views import (
    SaveResumeView, MyResumesView, CurrentUserView,
    TemplateListView, SaveTemplateView, MyTemplatesView, FavoriteTemplateView,
    UserSelectedTemplateView, WorkspaceView, DeleteResumeView, DuplicateResumeView,
    ForgotPasswordView, RecoveryCodeView, ResetPasswordConfirmView, ResetPasswordSuccessView
)

def home(request):
    return HttpResponse("Django backend running")

urlpatterns = [
    path('admin/', admin.site.urls),
    path('accounts/password/reset/', ForgotPasswordView.as_view(), name='account_reset_password'),
    path('accounts/password/reset/code/', RecoveryCodeView.as_view(), name='account_reset_password_code'),
    path('accounts/password/reset/confirm/', ResetPasswordConfirmView.as_view(), name='account_reset_password_confirm'),
    path('accounts/password/reset/success/', ResetPasswordSuccessView.as_view(), name='account_reset_password_success'),
    path('accounts/', include('allauth.urls')),
    path('api/save-resume/', SaveResumeView.as_view(), name='save-resume'),
    path('api/my-resumes/', MyResumesView.as_view(), name='my-resumes'),
    path('api/me/', CurrentUserView.as_view(), name='current-user'),
    path('api/me/selected-template/', UserSelectedTemplateView.as_view(), name='selected-template'),
    path('api/workspace/', WorkspaceView.as_view(), name='workspace'),
    path('api/delete-resume/<int:id>/', DeleteResumeView.as_view(), name='delete-resume'),
    path('api/duplicate-resume/<int:id>/', DuplicateResumeView.as_view(), name='duplicate-resume'),

    
    # Template Library APIs
    path('api/templates/', TemplateListView.as_view(), name='template-list'),
    path('api/templates/save/<int:id>/', SaveTemplateView.as_view(), name='save-template'),
    path('api/my-templates/', MyTemplatesView.as_view(), name='my-templates'),
    path('api/templates/favorite/<int:id>/', FavoriteTemplateView.as_view(), name='favorite-template'),
    
    path('dashboard/', lambda request: HttpResponse("Dashboard"), name='dashboard'),
    path('', home, name='home'),
]

