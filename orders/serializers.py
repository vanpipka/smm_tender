from rest_framework import serializers
from .models import Order, Cargo, OrderFile, OrderAccess


class OrderFileSerializer(serializers.ModelSerializer):
    class Meta:
        model = OrderFile
        fields = ['id', 'file', 'name', 'uploaded_at']
        read_only_fields = ['id', 'uploaded_at']


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
            'departure_period', 'deleted', 'total_weight', 'cargoes',
            'payment_terms', 'delivery_terms'
        ]

    def create(self, validated_data):
        # Извлекаем данные грузов из запроса, если они есть
        cargoes_data = validated_data.pop('cargoes', [])
        allowed_users = validated_data.pop('allowed_users', None)

        # Создаем сам заказ
        order = Order.objects.create(**validated_data)
        
        # Создаем связанные грузы
        for cargo_data in cargoes_data:
            Cargo.objects.create(order=order, **cargo_data)

        # Создаем связанные пользователи с доступом
        if allowed_users is not None:
            self._sync_user_accesses(order, allowed_users)

        return order

    def update(self, instance, validated_data):
        # Извлекаем данные грузов, если они переданы в запросе
        cargoes_data = validated_data.pop('cargoes', None)
        allowed_users = validated_data.pop('allowed_users', None)

        # 1. Обновляем основные поля заказа
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        # 2. Обрабатываем вложенные грузы (если они переданы)
        if cargoes_data is not None:
            # Стратегия: простой и надежный подход — удалить старые грузы и создать переданные заново.
            # (Либо можно обновлять по ID, если это критично для вашей бизнес-логики)
            instance.cargoes.all().delete()
            for cargo_data in cargoes_data:
                Cargo.objects.create(order=instance, **cargo_data)


        # 3. Обновляем доступ пользователей (если передан список)
        if allowed_users is not None:
            self._sync_user_accesses(instance, allowed_users)
            
        return instance

    def _sync_user_accesses(self, order, users):
        """Синхронизирует записи в промежуточной таблице OrderAccess с сохранением granted_by."""
        request = self.context.get("request")

        target_user_ids = {user.id for user in users}
        existing_user_ids = set(
            order.user_accesses.values_list("user_id", flat=True)
        )

        # Удаляем доступ у тех, кого убрали из списка
        to_remove = existing_user_ids - target_user_ids
        if to_remove:
            order.user_accesses.filter(user_id__in=to_remove).delete()

        # Добавляем доступ новым пользователям
        to_add = target_user_ids - existing_user_ids
        if to_add:
            OrderAccess.objects.bulk_create([
                OrderAccess(order=order, user_id=user_id)
                for user_id in to_add
            ])