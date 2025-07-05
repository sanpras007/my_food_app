from django.db import models
from django.contrib.auth.models import User

class Item(models.Model):
    sr_no = models.PositiveIntegerField(unique=True, blank=True, null=True)
    name = models.CharField(max_length=100)
    price = models.DecimalField(max_digits=6, decimal_places=2)
    description = models.TextField(blank=True)

    def __str__(self):
        return self.name

class Order(models.Model):
    sr_no = models.PositiveIntegerField(unique=True, blank=True, null=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    ordered_at = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=20, default='PENDING')

    def __str__(self):
        return f"Order #{self.sr_no or self.id} by {self.user.username}"
    
    def save(self, *args, **kwargs):
        if not self.sr_no:
            last_sr = Order.objects.aggregate(models.Max('sr_no'))['sr_no__max'] or 0
            self.sr_no = last_sr + 1
        super().save(*args, **kwargs)

    @property
    def total_amount(self):
        return sum(item.total_price for item in self.order_items.all())

class OrderItem(models.Model):
    order = models.ForeignKey(Order, related_name='order_items', on_delete=models.CASCADE)
    item = models.ForeignKey(Item, on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField(default=1)
    price_at_order = models.DecimalField(max_digits=8, decimal_places=2)  # snapshot

    @property
    def total_price(self):
        return self.price_at_order * self.quantity

    def __str__(self):
        return f"{self.quantity} x {self.item.name} in Order #{self.order.id}"