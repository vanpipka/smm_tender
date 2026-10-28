from django.db import models
from django.conf import settings


class Order(models.Model):
    # Поле Id создается Django автоматически как Primary Key (BigAutoField),
    # но при необходимости можно явно указать кастомное поле.
    
    number = models.CharField(max_length=100, verbose_name="Номер")
    date = models.DateField(verbose_name="Дата")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Дата создания")
    
    recipient = models.CharField(max_length=255, verbose_name="Получатель")
    recipient_address = models.TextField(verbose_name="Адрес получателя")
    
    sender = models.CharField(max_length=255, verbose_name="Отправитель")
    sender_address = models.TextField(verbose_name="Адрес отправителя")
    
    initial_price = models.DecimalField(max_digits=12, decimal_places=2, verbose_name="Начальная цена")
    price_step = models.DecimalField(max_digits=12, decimal_places=2, verbose_name="Шаг цены")
    
    tender_opening_date = models.DateTimeField(verbose_name="Дата открытия тендера")
    time_to_end = models.PositiveIntegerField(verbose_name="Продление торгов (мин.)", default=5)
    tender_ending_date = models.DateTimeField(verbose_name="Дата окончания тендера")
    
    arrivals_custom = models.CharField(max_length=255, blank=True, null=True, verbose_name="Таможня прибытия")
    departures_custom = models.CharField(max_length=255, blank=True, null=True, verbose_name="Таможня отправления")
    
    cargo_cost = models.DecimalField(max_digits=12, decimal_places=2, blank=True, null=True, verbose_name="Стоимость груза")
    cargo_currency = models.CharField(max_length=10, default='RUB', verbose_name="Валюта груза")
    tender_currency = models.CharField(max_length=10, default='RUB', verbose_name="Валюта тендера")
    
    arrival_period = models.CharField(max_length=100, blank=True, null=True, verbose_name="Период прибытия")
    departure_period = models.CharField(max_length=100, blank=True, null=True, verbose_name="Период отправления")
    
    deleted = models.BooleanField(default=False, verbose_name="Удален")

    @property
    def total_weight(self):
        """Суммарный вес всех грузов заказа"""
        return sum(cargo.count * cargo.weight_per_unit for cargo in self.cargoes.all())
    
    class Meta:
        verbose_name = "Заказ / Тендер"
        verbose_name_plural = "Заказы / Тендеры"
        ordering = ['-created_at']

    def __str__(self):
        return f"Заказ №{self.number} от {self.date}"


class Cargo(models.Model):
    # Id создается автоматически Django (BigAutoField)
    name = models.CharField(max_length=255, verbose_name="Наименование груза")
    count = models.PositiveIntegerField(verbose_name="Количество")
    size = models.CharField(max_length=100, blank=True, null=True, verbose_name="Размер (Габариты)")
    weight_per_unit = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Вес за единицу")
    
    # BookingId -> Ссылка на Order (заказ/тендер)
    order = models.ForeignKey(
        Order, 
        on_delete=models.CASCADE, 
        related_name='cargoes', 
        verbose_name="Заказ"
    )
    
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Дата создания")

    class Meta:
        verbose_name = "Груз"
        verbose_name_plural = "Грузы"
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.name} ({self.count} шт.)"
    

class Bid(models.Model):
    # Клиент/исполнитель, сделавший ставку (ссылка на стандартную модель User)
    client = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.CASCADE, 
        related_name='bids',
        verbose_name="Клиент / Исполнитель"
    )
    
    # Заявка / Тендер, на который делается ставка
    order = models.ForeignKey(
        Order, 
        on_delete=models.CASCADE, 
        related_name='bids',
        verbose_name="Заявка"
    )
    
    # Сумма ставки
    amount = models.DecimalField(
        max_digits=12, 
        decimal_places=2, 
        verbose_name="Сумма ставки"
    )
    
    # Дата и время создания ставки (проставляется автоматически)
    created_at = models.DateTimeField(
        auto_now_add=True, 
        verbose_name="Дата создания"
    )

    class Meta:
        verbose_name = "Ставка"
        verbose_name_plural = "Ставки"
        ordering = ['-created_at']  # Свежие ставки сверху

    def __str__(self):
        return f"Ставка {self.amount} от {self.client.username} на заказ №{self.order.number}"