from django import forms
from .models import Item
from .models import AppSetting

class ItemForm(forms.ModelForm):
    class Meta:
        model = Item
        fields = ['name', 'price']

class AppSettingForm(forms.ModelForm):
    class Meta:
        model = AppSetting
        fields = ['allow_order_deletion']
