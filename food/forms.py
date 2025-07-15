from django import forms
from .models import Item
from .models import AppSetting
from django.contrib.auth.models import User

class ItemForm(forms.ModelForm):
    class Meta:
        model = Item
        fields = ['name', 'price']

class AppSettingForm(forms.ModelForm):
    class Meta:
        model = AppSetting
        fields = ['allow_order_deletion']

class EmailUpdateForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ['email']