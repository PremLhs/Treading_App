from django import forms
from django.contrib.auth import authenticate
from django.contrib.auth.models import User
from .models import UserProfile


class LoginForm(forms.Form):
    login = forms.CharField(
        max_length=150,
        widget=forms.TextInput(attrs={
            "class": "form-input",
            "placeholder": "Email ID or Mobile Number"
        })
    )

    password = forms.CharField(
        widget=forms.PasswordInput(attrs={
            "class": "form-input",
            "placeholder": "Password"
        })
    )

    def __init__(self, request=None, *args, **kwargs):
        self.request = request
        self.user_cache = None
        super().__init__(*args, **kwargs)

    def clean(self):
        cleaned_data = super().clean()
        login_value = (cleaned_data.get("login") or "").strip()
        password = cleaned_data.get("password")

        if not login_value or not password:
            return cleaned_data

        user = None

        if "@" in login_value:
            try:
                matched_user = User.objects.get(email__iexact=login_value)
                user = authenticate(
                    request=self.request,
                    username=matched_user.username,
                    password=password
                )
            except User.DoesNotExist:
                user = None
        else:
            try:
                profile = UserProfile.objects.select_related("user").get(
                    mobile=login_value
                )
                user = authenticate(
                    request=self.request,
                    username=profile.user.username,
                    password=password
                )
            except UserProfile.DoesNotExist:
                user = None

        if user is None:
            raise forms.ValidationError(
                "Invalid Email/Mobile Number or Password."
            )

        if not user.is_active:
            raise forms.ValidationError(
                "Your account has been disabled."
            )

        self.user_cache = user
        return cleaned_data

    def get_user(self):
        return self.user_cache


from django import forms


class WhatsAppBroadcastForm(forms.Form):
    message = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={
            "class": "form-textarea",
            "rows": 6,
            "placeholder": "Type your broadcast message here..."
        })
    )
    attachment = forms.FileField(
        required=False,
        widget=forms.ClearableFileInput(attrs={
            "class": "form-input-file",
            "accept": ".jpg,.jpeg,.png,.pdf,.doc,.docx,.xls,.xlsx,.txt,.csv,.mp4"
        })
    )

    def clean(self):
        cleaned_data = super().clean()
        message = (cleaned_data.get("message") or "").strip()
        attachment = cleaned_data.get("attachment")

        if not message and not attachment:
            raise forms.ValidationError("Message ya attachment me se kam se kam ek dena zaroori hai.")

        return cleaned_data
    



#################################################################################################

from django import forms


class WhatsAppCSVUploadForm(forms.Form):
    csv_file = forms.FileField(
        widget=forms.ClearableFileInput(attrs={"class": "form-control"})
    )

    def clean_csv_file(self):
        file = self.cleaned_data["csv_file"]
        if not file.name.lower().endswith(".csv"):
            raise forms.ValidationError("Only CSV file is allowed.")
        return file


class WhatsAppBroadcastForm(forms.Form):
    message = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={
            "class": "form-control",
            "rows": 7,
            "placeholder": "Type message here..."
        })
    )
    attachment = forms.FileField(
        required=False,
        widget=forms.ClearableFileInput(attrs={"class": "form-control"})
    )

    def clean(self):
        cleaned_data = super().clean()
        message = cleaned_data.get("message")
        attachment = cleaned_data.get("attachment")

        if not message and not attachment:
            raise forms.ValidationError("Message or attachment is required.")

        return cleaned_data