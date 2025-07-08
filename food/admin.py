from django.contrib import admin
from .models import Item, Order
from .models import AppSetting

@admin.register(AppSetting)
class AppSettingAdmin(admin.ModelAdmin):
    list_display = ('allow_order_deletion',)

# Register your models here.
admin.site.register(Item)
admin.site.register(Order)

