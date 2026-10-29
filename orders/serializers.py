from rest_framework import serializers
from .models import Order, Cargo

class CargoSerializer(serializers.ModelSerializer):
    class Meta:
        model = Cargo
        fields = ['id', 'name', 'count', 'size', 'weight_per_unit']


class OrderSerializer(serializers.ModelSerializer):
    # Вложенный сериализатор для создания/получения грузов (связан через related_name='cargoes')
    cargoes = CargoSerializer(many=True, required=False)
    total_weight = serializers.ReadOnlyField() # Свойство-считалка доступно только для чтения

    class Meta:
        model = Order
        fields = [
            'id', 'number', 'date', 'recipient', 'recipient_address',
            'sender', 'sender_address', 'initial_price', 'price_step',
            'tender_opening_date', 'time_to_end', 'tender_ending_date',
            'arrivals_custom', 'departures_custom', 'cargo_cost',
            'cargo_currency', 'tender_currency', 'arrival_period',
            'departure_period', 'deleted', 'total_weight', 'cargoes'
        ]

    def create(self, validated_data):
        # Извлекаем данные грузов из запроса, если они есть
        cargoes_data = validated_data.pop('cargoes', [])
        
        # Создаем сам заказ
        order = Order.objects.create(**validated_data)
        
        # Создаем связанные грузы
        for cargo_data in cargoes_data:
            Cargo.objects.create(order=order, **cargo_data)
            
        return order