from django import forms
from django.contrib.auth.models import User
from django.contrib.auth.forms import AuthenticationForm

class RegisterForm(forms.ModelForm):
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={"class": "form-input", "placeholder": "Password"})
    )
    confirm_password = forms.CharField(
        widget=forms.PasswordInput(attrs={"class": "form-input", "placeholder": "Confirm Password"})
    )

    class Meta:
        model = User
        fields = ["username"]
        widgets = {
            "username": forms.TextInput(attrs={"class": "form-input", "placeholder": "Username"})
        }

    def clean_username(self):
        username = self.cleaned_data["username"]
        if User.objects.filter(username=username).exists():
            raise forms.ValidationError("Username already exists.")
        return username

    def clean(self):
        cleaned_data = super().clean()
        password = cleaned_data.get("password")
        confirm_password = cleaned_data.get("confirm_password")
        if password and confirm_password and password != confirm_password:
            raise forms.ValidationError("Passwords do not match.")
        return cleaned_data


class LoginForm(AuthenticationForm):
    username = forms.CharField(
        widget=forms.TextInput(attrs={"class": "form-input", "placeholder": "Username"})
    )
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={"class": "form-input", "placeholder": "Password"})
    )



from django import forms
from django.contrib.auth import authenticate
from django.contrib.auth.models import User
from .models import UserProfile

class RegisterForm(forms.Form):
    username = forms.CharField(
        max_length=100,
        widget=forms.TextInput(attrs={"placeholder": "Enter username"})
    )
    mobile = forms.CharField(
        max_length=15,
        widget=forms.TextInput(attrs={"placeholder": "Enter mobile number"})
    )
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={"placeholder": "Enter password"})
    )
    confirm_password = forms.CharField(
        widget=forms.PasswordInput(attrs={"placeholder": "Confirm password"})
    )

    def clean_username(self):
        username = self.cleaned_data["username"].strip()
        if User.objects.filter(username=username).exists():
            raise forms.ValidationError("Username already exists.")
        return username

    def clean_mobile(self):
        mobile = self.cleaned_data["mobile"].strip()
        if not mobile.isdigit():
            raise forms.ValidationError("Mobile number must contain digits only.")
        if len(mobile) < 10 or len(mobile) > 15:
            raise forms.ValidationError("Enter a valid mobile number.")
        if UserProfile.objects.filter(mobile=mobile).exists():
            raise forms.ValidationError("Mobile number already registered.")
        return mobile

    def clean(self):
        cleaned_data = super().clean()
        password = cleaned_data.get("password")
        confirm_password = cleaned_data.get("confirm_password")

        if password and confirm_password and password != confirm_password:
            self.add_error("confirm_password", "Passwords do not match.")

        return cleaned_data

    def save(self):
        username = self.cleaned_data["username"]
        mobile = self.cleaned_data["mobile"]
        password = self.cleaned_data["password"]

        user = User.objects.create_user(
            username=username,
            password=password
        )

        UserProfile.objects.create(
            user=user,
            mobile=mobile
        )

        return user


class LoginForm(forms.Form):
    mobile = forms.CharField(
        max_length=15,
        widget=forms.TextInput(attrs={"placeholder": "Enter mobile number"})
    )
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={"placeholder": "Enter password"})
    )

    def __init__(self, request=None, *args, **kwargs):
        self.request = request
        self.user_cache = None
        super().__init__(*args, **kwargs)

    def clean_mobile(self):
        mobile = self.cleaned_data["mobile"].strip()
        if not mobile.isdigit():
            raise forms.ValidationError("Mobile number must contain digits only.")
        return mobile

    def clean(self):
        cleaned_data = super().clean()
        mobile = cleaned_data.get("mobile")
        password = cleaned_data.get("password")

        if mobile and password:
            try:
                profile = UserProfile.objects.select_related("user").get(mobile=mobile)
                user = authenticate(
                    request=self.request,
                    username=profile.user.username,
                    password=password
                )
            except UserProfile.DoesNotExist:
                user = None

            if user is None:
                raise forms.ValidationError("Invalid mobile number or password.")

            self.user_cache = user

        return cleaned_data

    def get_user(self):
        return self.user_cache


class ForgotPasswordForm(forms.Form):
    mobile = forms.CharField(
        max_length=15,
        widget=forms.TextInput(attrs={"placeholder": "Enter registered mobile number"})
    )
    new_password = forms.CharField(
        widget=forms.PasswordInput(attrs={"placeholder": "Enter new password"})
    )
    confirm_password = forms.CharField(
        widget=forms.PasswordInput(attrs={"placeholder": "Confirm new password"})
    )

    def clean_mobile(self):
        mobile = self.cleaned_data["mobile"].strip()
        if not mobile.isdigit():
            raise forms.ValidationError("Mobile number must contain digits only.")
        return mobile

    def clean(self):
        cleaned_data = super().clean()
        mobile = cleaned_data.get("mobile")
        new_password = cleaned_data.get("new_password")
        confirm_password = cleaned_data.get("confirm_password")

        if new_password and confirm_password and new_password != confirm_password:
            self.add_error("confirm_password", "Passwords do not match.")

        if mobile:
            if not UserProfile.objects.filter(mobile=mobile).exists():
                self.add_error("mobile", "No account found with this mobile number.")

        return cleaned_data

    def save(self):
        mobile = self.cleaned_data["mobile"]
        new_password = self.cleaned_data["new_password"]

        profile = UserProfile.objects.select_related("user").get(mobile=mobile)
        user = profile.user
        user.set_password(new_password)
        user.save()
        return user