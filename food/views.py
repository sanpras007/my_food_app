from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth import authenticate, login
from django.views.decorators.http import require_POST
from django.db.models import Sum
from django.contrib.auth.models import User
from django.contrib import messages
from .models import *
from .forms import *
from django.contrib.auth import logout
from django.utils.timezone import make_aware
from django.utils.timezone import now
from datetime import datetime
from django.shortcuts import get_object_or_404
from django.utils.dateparse import parse_date
from django.http import HttpResponse
from django.contrib.auth.decorators import user_passes_test
from django.contrib.auth import update_session_auth_hash
from .utils import send_verification_email
from django.utils import timezone
from datetime import timedelta
import google.generativeai as genai
from django.http import JsonResponse
import json
import csv
import uuid


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
            UserProfile.objects.get_or_create(user=user)
            send_verification_email(user)
            messages.success(request, 'Account created! Please verify your email before logging in.')
            return redirect('login')

    return render(request, 'signup.html')

@login_required
def account_view(request):
    email_form = EmailUpdateForm(instance=request.user, data=request.POST if request.POST.get('form_type') == 'email_form' else None)
    toggle_form = None

    if request.user.is_staff:
        setting = AppSetting.objects.first()
        if not setting:
            setting = AppSetting.objects.create(allow_order_deletion=False)
        toggle_form = AppSettingForm(request.POST or None, instance=setting)

    if request.method == 'POST':
        form_type = request.POST.get('form_type')

        if form_type == 'email_form' and email_form.is_valid():
            email_form.save()
            # Optionally reset email_verified status here
            request.user.userprofile.email_verified = False
            request.user.userprofile.save()
            send_verification_email(request.user)
            messages.success(request, "Verification link sent to your email.")
            return redirect('account')

        elif form_type == 'toggle_form' and request.user.is_staff:
            if toggle_form and toggle_form.is_valid():
                toggle_form.save()
                messages.success(request, "Settings updated successfully.user can now delete orders.")
                return redirect('account')

    return render(request, 'account.html', {
        'email_form': email_form,
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

def verify_email(request):
    token = request.GET.get('token')
    if not token:
        return messages.error("Invalid or missing token")

    try:
        profile = UserProfile.objects.get(verification_token=token)
    except UserProfile.DoesNotExist:
        return HttpResponse("Invalid verification link", status=400)

    if timezone.now() > profile.token_expiry:
        return HttpResponse("Verification link has expired", status=400)

    profile.email_verified = True
    profile.verification_token = None
    profile.token_expiry = None
    profile.save()

    messages.success(request, "✅ Email verified successfully!")
    return redirect('/')

    
@login_required
def resend_verification(request):
    send_verification_email(request.user)
    messages.success(request, "Verification link sent to your email.")
    return redirect('account')


def process_voice_command(request):
    """
    Handles voice commands by routing them to the correct action based on AI-detected intent.
    This function manages a conversational loop by receiving and sending context.
    """
    if request.method == 'POST':
        audio_file = request.FILES.get('audio_command')
        # Load the conversational context sent from the frontend
        context = json.loads(request.POST.get('context', '{}'))

        if not audio_file:
            return JsonResponse({'status': 'error', 'message': 'No audio file found.'}, status=400)

        # --- Configure Gemini API ---
        GEMINI_API_KEY = "AIzaSyC3Gc6XCzQob5XlcSg058zOVB4g14IMb-c"
        genai.configure(api_key=GEMINI_API_KEY)
        model = genai.GenerativeModel('gemini-1.5-flash')

        audio_blob = {'mime_type': audio_file.content_type, 'data': audio_file.read()}

        # --- The Master Prompt for the Conversational Router ---
        prompt = f"""
        You are a conversational food ordering assistant. Your job is to understand the user's goal (their "intent") and extract key information ("entities").
        The user might be in the middle of a conversation, which is provided in the 'context'.

        # Available Intents:
        - add_to_cart: For adding items. Entities: list of items with name and quantity.
        - query_last_order: When the user asks to see, manage, or delete their last order.
        - confirm_action: When the user gives an affirmative response like "yes", "confirm", "do it".
        - cancel_action: When the user gives a negative response like "no", "cancel", "stop".
        - confirm_order: When the user wants to finalize the items currently in their cart.

        # Conversation Flow:
        1. After adding items, the context will be {{"action": "ask_anything_else"}}.
        2. If the user says "no" or "that's it", their intent is 'cancel_action'.
        3. When context is {{"action": "ask_anything_else"}} and intent is 'cancel_action', you will then ask for final order confirmation.
        4. When context is {{"action": "confirm_final_order"}} and intent is 'confirm_action', the order will be placed.

        # Input from user:
        - Audio command
        - Current conversation context: {json.dumps(context)}

        # Your Task:
        Return a single, clean JSON object describing the user's intent. Do not add any conversational text, explanations, or markdown formatting. Your entire response must be ONLY the JSON object.

        # Examples:
        1. User says: "add two samosas and a tea" -> Your Output: {{"intent": "add_to_cart", "items": [{{"name": "Samosa", "quantity": 2}}, {{"name": "Tea", "quantity": 1}}]}}
        2. User says: "can you delete my last order" -> Your Output: {{"intent": "query_last_order"}}
        3. User says: "yes confirm" (Context has action: "confirm_delete") -> Your Output: {{"intent": "confirm_action"}}
        """

        try:
            # --- Call Gemini and Clean the Response ---
            response = model.generate_content([prompt, audio_blob])
            raw_text = response.text
            clean_text = raw_text.strip().replace("```json", "").replace("```", "").strip()
            
            print(f"--- Gemini Cleaned Response: {clean_text} ---") # For debugging
            
            command_data = json.loads(clean_text)
            intent = command_data.get("intent")

            # --- Intent Routing Logic ---

            # 1. INTENT: Add items to the cart
            if intent == "add_to_cart":
                items_to_add = []
                unrecognized_items = []
                for item_data in command_data.get('items', []):
                    try:
                        item_obj = Item.objects.get(name__iexact=item_data.get('name'))
                        items_to_add.append({
                            "id": item_obj.id, "name": item_obj.name,
                            "price": float(item_obj.price), "qty": item_data.get('quantity')
                        })
                    except Item.DoesNotExist:
                        unrecognized_items.append(item_data.get('name'))
                
                spoken_response = "Added."
                if unrecognized_items:
                    spoken_response += f" I couldn't find {', '.join(unrecognized_items)}."
                
                # *** NEW: Ask if user wants to add more ***
                spoken_response += " Anything else?"

                return JsonResponse({
                    "frontend_action": "update_cart_and_speak",
                    "items": items_to_add,
                    "spoken_response": spoken_response,
                    "context": {"action": "ask_anything_else"} # Set context for the next step
                })

            # 2. INTENT: Start the 'delete last order' flow
            elif intent == "query_last_order":
                last_order = Order.objects.filter(user=request.user).order_by('-ordered_at').first()
                if not last_order:
                    return JsonResponse({"frontend_action": "speak", "spoken_response": "You don't have any past orders."})

                order_items = list(OrderItem.objects.filter(order=last_order).values('item__name', 'quantity'))
                item_descriptions = [f"{i['quantity']} {i['item__name']}" for i in order_items]
                
                # Ask the frontend to show details and request confirmation
                return JsonResponse({
                    "frontend_action": "ask_confirmation",
                    "spoken_response": f"Your last order included {', '.join(item_descriptions)}. Are you sure you want to delete it?",
                    "display_data": {"order_id": last_order.id, "items": order_items},
                    "context": {"action": "confirm_delete", "order_id": last_order.id}
                })

            # 3. INTENT: User confirms a pending action
            elif intent == "confirm_action":
                if context.get("action") == "confirm_final_order":
                    return JsonResponse({
                        "frontend_action": "submit_order_form",
                        "spoken_response": "Great. Placing your order now."
                    })
                elif context.get("action") == "confirm_delete":
                    order_id_to_delete = context.get("order_id")
                    Order.objects.filter(id=order_id_to_delete, user=request.user).delete()
                    return JsonResponse({
                        "frontend_action": "speak_and_refresh",
                        "spoken_response": "OK, I have deleted the order."
                    })
                else:
                    return JsonResponse({"frontend_action": "speak", "spoken_response": "I'm sorry, I lost track of what we were doing. Please start over."})


            # 4. INTENT: User cancels a pending action
            elif intent == "cancel_action":
                if context.get("action") == "ask_anything_else":
                    return JsonResponse({
                        "frontend_action": "speak",
                        "spoken_response": "Got it. Should I confirm the order?",
                        "context": {"action": "confirm_final_order"}
                    })
                else:
                    # Default cancel action
                    return JsonResponse({
                        "frontend_action": "speak",
                        "spoken_response": "OK. I've cancelled the action.",
                        "context": {}
                    })

            # Fallback for unknown intents
            else:
                return JsonResponse({"frontend_action": "speak", "spoken_response": "Sorry, I'm not sure how to do that yet."})

        except json.JSONDecodeError:
            return JsonResponse({'status': 'error', 'message': f"Invalid JSON from AI. Raw response was: {response.text}"})
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': f"An unexpected backend error occurred: {str(e)}"})

    return JsonResponse({'status': 'error', 'message': 'Invalid request method.'}, status=405)