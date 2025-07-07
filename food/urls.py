from django.urls import path
from . import views

urlpatterns = [
    path('', views.home, name='home'),
    path('login/', views.user_login, name='login'),
    path('signup/', views.user_signup, name='signup'),
    path('add-item/', views.add_item, name='add_item'),
    path('logout/', views.user_logout, name='logout'),
    path('edit-item/<int:item_id>/', views.edit_item, name='edit_item'),
    path('delete-item/<int:item_id>/', views.delete_item, name='delete_item'),
    path('confirm-order/', views.confirm_order, name='confirm_order'),
    path('orders/', views.user_orders, name='orders'),
    path('orders/delete/<int:order_id>/', views.delete_order, name='delete_order'),
    path('orders/create/', views.create_custom_order, name='create_order'),
    path('reports/', views.report_view, name='reports'),

]
