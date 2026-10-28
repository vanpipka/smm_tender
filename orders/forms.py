from django import forms
from django.utils import timezone
from django.db.models import Min
from .models import Bid


class BidForm(forms.ModelForm):
    class Meta:
        model = Bid
        fields = ['amount']
        widgets = {
            'amount': forms.NumberInput(attrs={
                'class': 'form-control',
                'placeholder': 'Введите сумму ставки'
            })
        }

    def __init__(self, *args, **kwargs):
        self.order = kwargs.pop('order', None)
        super().__init__(*args, **kwargs)

    def clean_amount(self):
        amount = self.cleaned_data.get('amount')
        if not self.order:
            return amount

        now = timezone.now()

        # 1. Проверка, что торги находятся в активной фазе
        if not (self.order.tender_opening_date and self.order.tender_ending_date):
            raise forms.ValidationError("Сроки проведения торгов не установлены.")
        
        if now < self.order.tender_opening_date:
            raise forms.ValidationError("Торги еще не начались.")
        
        if now > self.order.tender_ending_date:
            raise forms.ValidationError("Торги уже завершены.")

        # 2. Определяем базу для расчета: текущая минимальная ставка или базовая цена
        lowest_bid = self.order.bids.aggregate(Min('amount'))['amount__min']
        baseline = lowest_bid if lowest_bid is not None else self.order.initial_price

        if baseline is None:
            raise forms.ValidationError("Для этого заказа не задана базовая цена.")

        # 3. Максимально допустимая ставка = база - шаг цены
        max_allowed_bid = baseline - self.order.price_step

        if amount > max_allowed_bid:
            raise forms.ValidationError(
                f"Ставка должна быть не выше {max_allowed_bid} {self.order.tender_currency} "
                f"(текущая/базовая цена {baseline} минус шаг цены {self.order.price_step})."
            )

        return amount
    