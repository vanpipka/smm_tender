from django.contrib import admin
from .models import Order, Cargo, Bid, OrderAccess, OrderFile


class OrderAccessInline(admin.TabularInline):
    """Встроенная таблица выдачи прав внутри карточки заказа."""
    model = OrderAccess
    fk_name = "order"  # Обязательно, т.к. у OrderAccess есть FK на Order (если их несколько)
    extra = 1
    autocomplete_fields = ["user"]  # Удобный поиск пользователя (требует search_fields в UserAdmin)
    fields = ["user"]


class CargoInline(admin.TabularInline):
    """Позволяет добавлять и редактировать грузы прямо внутри страницы Заказа"""
    model = Cargo
    extra = 1


class OrderFileInline(admin.TabularInline):
    model = OrderFile
    extra = 1
    readonly_fields = ['uploaded_at']
    

@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ('number', 'date', 'sender', 'recipient', 'initial_price', 'tender_currency', 'deleted')
    list_filter = ('deleted', 'tender_currency', 'date')
    search_fields = ('number', 'sender', 'recipient')
    inlines = [CargoInline, OrderFileInline, OrderAccessInline]  # Подключаем грузы, файлы и доступ пользователей таблицей внутрь заказа

    def get_queryset(self, request):
        return super().get_queryset(request).prefetch_related("user_accesses", "cargoes", "files")

    @admin.display(description="Пользователей с доступом")
    def get_allowed_users_count(self, obj):
        return obj.user_accesses.count()


@admin.register(Cargo)
class CargoAdmin(admin.ModelAdmin):
    list_display = ('name', 'order', 'count', 'weight_per_unit', 'created_at')
    list_filter = ('created_at',)
    search_fields = ('name', 'order__number')


@admin.register(OrderFile)
class OrderFileAdmin(admin.ModelAdmin):
    list_display = ['id', 'order', 'name', 'uploaded_at']
    list_filter = ['uploaded_at']
    search_fields = ['name', 'order__number']


@admin.register(Bid)
class BidAdmin(admin.ModelAdmin):
    list_display = ('order', 'client', 'amount', 'created_at')
    list_filter = ('created_at', 'order')
    search_fields = ('client__username', 'order__number')