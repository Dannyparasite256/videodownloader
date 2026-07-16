"""Account forms."""
from __future__ import annotations

from django import forms
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm
from django.contrib.auth import get_user_model

User = get_user_model()


class RegisterForm(UserCreationForm):
    email = forms.EmailField(required=True, widget=forms.EmailInput(attrs={
        "class": "form-input",
        "placeholder": "you@example.com",
        "autocomplete": "email",
    }))

    class Meta:
        model = User
        fields = ("username", "email", "password1", "password2")
        widgets = {
            "username": forms.TextInput(attrs={
                "class": "form-input",
                "placeholder": "username",
                "autocomplete": "username",
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["password1"].widget.attrs.update({
            "class": "form-input",
            "placeholder": "Password (min 10 chars)",
            "autocomplete": "new-password",
        })
        self.fields["password2"].widget.attrs.update({
            "class": "form-input",
            "placeholder": "Confirm password",
            "autocomplete": "new-password",
        })

    def clean_email(self) -> str:
        email = self.cleaned_data["email"].lower().strip()
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError("An account with this email already exists.")
        return email


class LoginForm(AuthenticationForm):
    username = forms.CharField(widget=forms.TextInput(attrs={
        "class": "form-input",
        "placeholder": "Username or email",
        "autocomplete": "username",
    }))
    password = forms.CharField(widget=forms.PasswordInput(attrs={
        "class": "form-input",
        "placeholder": "Password",
        "autocomplete": "current-password",
    }))


class ProfileForm(forms.ModelForm):
    class Meta:
        model = User
        fields = (
            "first_name",
            "last_name",
            "email",
            "bio",
            "avatar",
            "theme",
            "accent_color",
            "email_notifications",
            "browser_notifications",
            "default_video_quality",
            "default_audio_quality",
            "default_format",
            "preferred_filename_template",
            "bandwidth_limit_kbps",
        )
        widgets = {
            "first_name": forms.TextInput(attrs={"class": "form-input"}),
            "last_name": forms.TextInput(attrs={"class": "form-input"}),
            "email": forms.EmailInput(attrs={"class": "form-input"}),
            "bio": forms.TextInput(attrs={"class": "form-input", "maxlength": 280}),
            "theme": forms.Select(attrs={"class": "form-input"}),
            "accent_color": forms.TextInput(attrs={"class": "form-input", "type": "color"}),
            "default_video_quality": forms.Select(
                choices=[
                    ("best", "Highest Available"),
                    ("worst", "Lowest Available"),
                    ("2160", "4K (2160p)"),
                    ("1440", "1440p"),
                    ("1080", "1080p"),
                    ("720", "720p"),
                    ("480", "480p"),
                    ("360", "360p"),
                ],
                attrs={"class": "form-input"},
            ),
            "default_audio_quality": forms.Select(
                choices=[
                    ("best", "Best"),
                    ("320", "320 kbps"),
                    ("256", "256 kbps"),
                    ("192", "192 kbps"),
                    ("128", "128 kbps"),
                    ("96", "96 kbps"),
                    ("64", "64 kbps"),
                ],
                attrs={"class": "form-input"},
            ),
            "default_format": forms.Select(
                choices=[
                    ("mp4", "MP4"),
                    ("mkv", "MKV"),
                    ("webm", "WEBM"),
                    ("mp3", "MP3"),
                    ("m4a", "M4A"),
                    ("flac", "FLAC"),
                ],
                attrs={"class": "form-input"},
            ),
            "preferred_filename_template": forms.TextInput(attrs={"class": "form-input"}),
            "bandwidth_limit_kbps": forms.NumberInput(attrs={"class": "form-input", "min": 0}),
        }
