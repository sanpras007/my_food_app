from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth import authenticate, login
from django.views.decorators.http import require_POST
from django.contrib.auth.models import User
from django.contrib import messages
from .models import *
from .forms import ItemForm
from django.contrib.auth import logout
from django.shortcuts import get_object_or_404


def user_logout(request):
    logout(request)
    return redirect('login')

def is_admin(user):
    return user.is_authenticated and user.is_staff

@user_passes_test(is_admin)
def report_view(request):
    users = User.objects.all()
    orders = []
    selected_user = None
    from_date = None
    to_date = None

    if request.method == 'GET':
        selected_user_id = request.GET.get('user')
        from_date = request.GET.get('from_date')
        to_date = request.GET.get('to_date')

        orders = Order.objects.all()

        if selected_user_id:
            selected_user = User.objects.filter(id=selected_user_id).first()
            orders = orders.filter(user=selected_user)

        if from_date:
            orders = orders.filter(ordered_at__date__gte=from_date)

        if to_date:
            orders = orders.filter(ordered_at__date__lte=to_date)

        orders = orders.order_by('-ordered_at')

    context = {
        'orders': orders,
        'users': users,
        'selected_user_id': int(selected_user.id) if selected_user else '',
        'from_date': from_date,
        'to_date': to_date,
    }
    return render(request, 'report.html', context)

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
    if request.method == 'POST':
        form = ItemForm(request.POST, request.FILES)
        if form.is_valid():
            form.save()
            return redirect('home')
    else:
        form = ItemForm()
    return render(request, 'add_item.html', {'form': form})

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
    orders = Order.objects.filter(user=request.user).order_by('-ordered_at')
    return render(request, 'orders.html', {'orders': orders})

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
        is_admin = request.POST.get('is_admin') == 'on'

        if User.objects.filter(username=username).exists():
            messages.error(request, 'Username already exists.')
        else:
            user = User.objects.create_user(username=username, email=email, password=password,is_staff=is_admin)
            login(request, user)
            return redirect('home')

    return render(request, 'signup.html')

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
