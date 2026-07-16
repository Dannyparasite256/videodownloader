"""Account views: register, login, profile, settings, API keys."""
from __future__ import annotations

from django.contrib import messages
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LoginView, PasswordResetView
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect, render
from django.urls import reverse_lazy
from django.views.decorators.http import require_http_methods, require_POST

from .forms import LoginForm, ProfileForm, RegisterForm
from .models import APIKey, ActivityLog


class AppLoginView(LoginView):
    template_name = "accounts/login.html"
    authentication_form = LoginForm
    redirect_authenticated_user = True

    def form_valid(self, form):
        response = super().form_valid(form)
        ActivityLog.objects.create(
            user=self.request.user,
            action=ActivityLog.Action.LOGIN,
            ip_address=self.request.META.get("REMOTE_ADDR"),
            user_agent=self.request.META.get("HTTP_USER_AGENT", "")[:512],
        )
        return response


@require_http_methods(["GET", "POST"])
def register(request: HttpRequest) -> HttpResponse:
    if request.user.is_authenticated:
        return redirect("downloads:home")
    form = RegisterForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = form.save()
        login(request, user, backend="django.contrib.auth.backends.ModelBackend")
        messages.success(request, "Welcome! Your account has been created.")
        return redirect("downloads:home")
    return render(request, "accounts/register.html", {"form": form})


@require_POST
@login_required
def logout_view(request: HttpRequest) -> HttpResponse:
    ActivityLog.objects.create(
        user=request.user,
        action=ActivityLog.Action.LOGOUT,
        ip_address=request.META.get("REMOTE_ADDR"),
    )
    logout(request)
    messages.info(request, "You have been signed out.")
    return redirect("downloads:home")


@login_required
@require_http_methods(["GET", "POST"])
def profile(request: HttpRequest) -> HttpResponse:
    form = ProfileForm(request.POST or None, request.FILES or None, instance=request.user)
    if request.method == "POST" and form.is_valid():
        form.save()
        ActivityLog.objects.create(
            user=request.user,
            action=ActivityLog.Action.PROFILE_UPDATE,
            description="Profile updated",
        )
        messages.success(request, "Profile saved.")
        return redirect("accounts:profile")
    return render(request, "accounts/profile.html", {"form": form})


@login_required
def settings_view(request: HttpRequest) -> HttpResponse:
    return render(request, "accounts/settings.html", {
        "api_keys": request.user.api_keys.filter(is_active=True),
        "activity": request.user.activity_logs.all()[:20],
    })


@login_required
@require_POST
def create_api_key(request: HttpRequest) -> HttpResponse:
    name = (request.POST.get("name") or "Default").strip()[:64]
    key_obj, raw = APIKey.generate(request.user, name)
    ActivityLog.objects.create(
        user=request.user,
        action=ActivityLog.Action.API_KEY_CREATE,
        description=f"Created API key: {name}",
        metadata={"key_id": str(key_obj.id)},
    )
    messages.success(
        request,
        f"API key created. Copy it now — it won't be shown again: {raw}",
    )
    return redirect("accounts:settings")


@login_required
@require_POST
def revoke_api_key(request: HttpRequest, key_id: str) -> HttpResponse:
    updated = request.user.api_keys.filter(id=key_id, is_active=True).update(is_active=False)
    if updated:
        ActivityLog.objects.create(
            user=request.user,
            action=ActivityLog.Action.API_KEY_REVOKE,
            description=f"Revoked API key {key_id}",
        )
        messages.success(request, "API key revoked.")
    return redirect("accounts:settings")


class AppPasswordResetView(PasswordResetView):
    template_name = "accounts/password_reset.html"
    email_template_name = "accounts/password_reset_email.html"
    success_url = reverse_lazy("accounts:password_reset_done")
