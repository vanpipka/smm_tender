from django.contrib import admin
from .models import Order, Cargo, Bid

class CargoInline(admin.TabularInline):
    """Позволяет добавлять и редактировать грузы прямо внутри страницы Заказа"""
    model = Cargo
    extra = 1

@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ('number', 'date', 'sender', 'recipient', 'initial_price', 'tender_currency', 'deleted')
    list_filter = ('deleted', 'tender_currency', 'date')
    search_fields = ('number', 'sender', 'recipient')
    inlines = [CargoInline]  # Подключаем грузы таблицей внутрь заказа

@admin.register(Cargo)
class CargoAdmin(admin.ModelAdmin):
    list_display = ('name', 'order', 'count', 'weight_per_unit', 'created_at')
    list_filter = ('created_at',)
    search_fields = ('name', 'order__number')


@admin.register(Bid)
class BidAdmin(admin.ModelAdmin):
    list_display = ('order', 'client', 'amount', 'created_at')
    list_filter = ('created_at', 'order')
    search_fields = ('client__username', 'order__number')