from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth import authenticate, login
from django.views.decorators.http import require_POST
from django.db.models import Sum
from django.contrib.auth.models import User
from django.contrib import messages
from .models import *
from .forms import ItemForm , AppSettingForm
from django.contrib.auth import logout
from django.utils.timezone import make_aware
from django.utils.timezone import now
from datetime import datetime
from django.shortcuts import get_object_or_404
from django.utils.dateparse import parse_date
from django.http import HttpResponse
from django.contrib.auth.decorators import user_passes_test
from django.contrib.auth.forms import PasswordChangeForm
from django.contrib.auth import update_session_auth_hash
import csv


def user_logout(request):
    logout(request)
    return redirect('login')

def is_admin(user):
    return user.is_authenticated and user.is_staff

@user_passes_test(is_admin)
def report_view(request):
    users = User.objects.all()
    orders = Order.objects.select_related('user').all()
    selected_user = None
    from_date = request.GET.get('from_date')
    to_date = request.GET.get('to_date')
    selected_user_id = request.GET.get('user')
    export_csv = request.GET.get('export') == 'csv'

    if selected_user_id:
        selected_user = User.objects.filter(id=selected_user_id).first()
        orders = orders.filter(user=selected_user)

    if from_date:
        orders = orders.filter(ordered_at__date__gte=from_date)

    if to_date:
        orders = orders.filter(ordered_at__date__lte=to_date)

    orders = orders.order_by('-ordered_at')
    total_amount = sum(order.total_amount for order in orders)

    # CSV Export
    if export_csv:
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="order_report.csv"'
        writer = csv.writer(response)
        writer.writerow([f"Report from {from_date or '...'} to {to_date or '...'}"])
        writer.writerow(['Order ID', 'User', 'Date', 'Total Amount', 'Status'])

        total_sum = 0
        for order in orders:
            writer.writerow([
                order.sr_no,
                order.user.username,
                order.ordered_at.strftime("%Y-%m-%d %H:%M"),
                f"₹{order.total_amount}",
                order.status
            ])
            total_sum += order.total_amount

        # Add a blank row and then the total row
        writer.writerow([])
        writer.writerow(['', '', '', 'Grand Total', f"₹{total_sum:.2f}"])

        return response

    context = {
        'orders': orders,
        'users': users,
        'selected_user_id': int(selected_user.id) if selected_user else '',
        'from_date': from_date,
        'to_date': to_date,
        'total_amount': total_amount,
    }
    return render(request, 'report.html', context)

@login_required
def create_custom_order(request):
    try:
        items = Item.objects.all()
        
        if request.method == 'POST':
            ordered_at_str = request.POST.get('order_date')
            ordered_at = datetime.strptime(ordered_at_str, '%Y-%m-%d')

            order = Order.objects.create(user=request.user, ordered_at=ordered_at)

            for item in items:
                qty = request.POST.get(f'qty_{item.id}')
                if qty and int(qty) > 0:
                    OrderItem.objects.create(
                        order=order,
                        item=item,
                        quantity=int(qty),
                        price_at_order=item.price
                    )
            return redirect('orders')

        return render(request, 'create_order.html', {
            'items': items,
            'now': now()
        })
    except Exception as e:
        from django.http import HttpResponse
        return HttpResponse(f"Error: {e}")

@login_required
def confirm_order(request):
    if request.method == 'POST':
        item_ids = request.POST.getlist('item_ids')
        if not item_ids:
            messages.error(request, "No items selected.")
            return redirect('home')

        order = Order.objects.create(user=request.user, status='SUCCESS')

        for item_id in item_ids:
            try:
                item = Item.objects.get(id=item_id)
                quantity = int(request.POST.get(f'qty_{item_id}', 1))
                OrderItem.objects.create(
                    order=order,
                    item=item,
                    quantity=quantity,
                    price_at_order=item.price
                )
            except Item.DoesNotExist:
                continue

        messages.success(request, "Order placed successfully!")
        return redirect('orders')


@user_passes_test(is_admin)
def add_item(request):
    items = None
    if request.method == 'POST':
        form = ItemForm(request.POST, request.FILES)
        if form.is_valid():
            form.save()
            return redirect('add_item')
    else:
        form = ItemForm()
        items = Item.objects.all()
    context = {
        'form': form,
        'items': items
    }
    return render(request, 'add_item.html', context)

@user_passes_test(is_admin)
@require_POST
def edit_item(request, item_id):
    item = get_object_or_404(Item, id=item_id)
    if request.method == 'POST':
        item.name = request.POST['name']
        item.price = request.POST['price']
        item.save()
        return redirect('home')

@login_required
def user_orders(request):
    orders = Order.objects.filter(user=request.user)
    from_date = request.GET.get('from_date')
    to_date = request.GET.get('to_date')

    if from_date:
        orders = orders.filter(ordered_at__date__gte=from_date)
    if to_date:
        # Add +1 day to include the whole 'to_date' day
        to_dt = parse_date(to_date)
        if to_dt:
            orders = orders.filter(ordered_at__date__lte=to_dt)
    app_settings = AppSetting.objects.first()
    orders = orders.order_by('-ordered_at')
    app_settings = AppSetting.objects.first()
    return render(request, 'orders.html', {'orders': orders,'app_settings': app_settings})

@login_required
def delete_order(request, order_id):
    order = get_object_or_404(Order, id=order_id, user=request.user)
    if request.method == 'POST':
        settings = AppSetting.objects.first()
        if not settings or not settings.allow_order_deletion:
            messages.error(request, "Please ask admin to turn on delete permission for this order from admin accounts menu.")
            return redirect('orders')
        order.delete()
        messages.success(request, f"Order #{order.sr_no} has been deleted.")
    return redirect('orders')

@user_passes_test(is_admin)
@require_POST
def delete_item(request, item_id):
    item = Item.objects.get(id=item_id)
    item.delete()
    return redirect('home')

def user_login(request):
    if request.method == 'POST':
        username = request.POST['username']
        password = request.POST['password']
        user = authenticate(request, username=username, password=password)
        if user:
            login(request, user)
            return redirect('home')
        else:
            messages.error(request, 'Invalid username or password.')
    return render(request, 'login.html')


def user_signup(request):
    if request.method == 'POST':
        username = request.POST['username']
        email = request.POST['email']
        password = request.POST['password']

        if User.objects.filter(username=username).exists():
            messages.error(request, 'Username already exists.')
        else:
            user = User.objects.create_user(username=username, email=email, password=password)
            login(request, user)
            return redirect('home')

    return render(request, 'signup.html')

@login_required
def account_view(request):
    password_form = PasswordChangeForm(user=request.user, data=request.POST or None)
    toggle_form = None

    if request.user.is_staff:
        setting = AppSetting.objects.first()
        if not setting:
            setting = AppSetting.objects.create(allow_order_deletion=False)
        toggle_form = AppSettingForm(request.POST or None, instance=setting)

    if request.method == 'POST':
        form_type = request.POST.get('form_type')

        if form_type == 'password_form':
            if password_form.is_valid():
                password_form.save()
                update_session_auth_hash(request, password_form.user)
                return redirect('account')

        elif form_type == 'toggle_form' and request.user.is_staff:
            if toggle_form and toggle_form.is_valid():
                toggle_form.save()
                messages.success(request, "Settings updated successfully.user can now delete orders.")
                return redirect('account')

    return render(request, 'account.html', {
        'form': password_form,
        'toggle_form': toggle_form,
        'user': request.user,
    })

@login_required(login_url='login')
def home(request):
    items = Item.objects.all()
    is_admin = request.user.is_authenticated and request.user.is_staff
    context = {
        'items':items,
        'is_admin':is_admin,
        'request':request.user
    }
    return render(request, 'home.html', context)
