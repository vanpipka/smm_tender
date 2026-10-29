from django.contrib.auth.decorators import login_required
from django.utils.decorators import method_decorator
from django.db.models import Min, OuterRef, Subquery
from django.db import models
from django.contrib import messages
from django.utils import timezone
from django.views.generic import ListView, DetailView
from django.http import JsonResponse
from datetime import timedelta
from django.shortcuts import get_object_or_404, redirect
from rest_framework import viewsets
from rest_framework.permissions import IsAdminUser
from .serializers import OrderSerializer
from .models import Order, Bid
from .forms import BidForm


@method_decorator(login_required, name='dispatch')
class OrderListView(ListView):
    model = Order
    template_name = 'orders/order_list.html'
    context_object_name = 'orders'
    paginate_by = 2  # Пагинация по 10 заказов на страницу (опционально)

    def get_queryset(self):
        user = self.request.user
        now = timezone.now()  # Текущее время с учетом настроек Django

        # Подзапрос для ставки пользователя
        user_bid_subquery = Bid.objects.filter(
            order=OuterRef('pk'), client=user
        ).values('amount')[:1]

        # Базовый queryset (не удаленные)
        queryset = Order.objects.filter(deleted=False).annotate(
            lowest_bid=Min('bids__amount'), user_bid=Subquery(user_bid_subquery)
        )

        # 1. Поиск по номеру заявки (если передан в GET)
        search_query = self.request.GET.get('search', '').strip()
        if search_query:
            queryset = queryset.filter(number__icontains=search_query)

        # 2. Фильтрация по статусу (active / finished)
        status_filter = self.request.GET.get('status', '').strip()
        if status_filter == 'active':
        # Активные: текущее время меньше или равно дате окончания торгов
            queryset = queryset.filter(tender_ending_date__gte=now)
        elif status_filter == 'finished':
        # Завершенные: текущее время больше даты окончания торгов
            queryset = queryset.filter(tender_ending_date__lt=now)

        return queryset.order_by('-created_at')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # Создаем копию GET-параметров запроса
        query_params = self.request.GET.copy()
        
        # Удаляем параметр page, если он там есть, чтобы избежать дублирования
        if 'page' in query_params:
            query_params.pop('page')
            
        # Превращаем оставшиеся параметры в строку (например: "search=test&status=active")
        query_string = query_params.urlencode()

        # Сохраняем параметры в контексте, чтобы подставлять их обратно в форму поиска/фильтров
        context['search_query'] = self.request.GET.get('search', '')
        context['selected_status'] = self.request.GET.get('status', '')
        context['query_string'] = f"&{query_string}" if query_string else ""

        if context['is_paginated']:
            page_obj = context['page_obj']

            context['page_range'] = page_obj.paginator.get_elided_page_range(
                number=page_obj.number
            )

        return context


@method_decorator(login_required, name='dispatch')
class OrderDetailView(DetailView):
    model = Order
    template_name = 'orders/order_detail.html'
    context_object_name = 'order'

    def get_queryset(self):
        user = self.request.user
        user_bid_subquery = Bid.objects.filter(
            order=OuterRef('pk'), client=user
        ).values('amount')[:1]

        return Order.objects.filter(deleted=False).annotate(
            lowest_bid=Min('bids__amount'),
            user_bid=Subquery(user_bid_subquery)
        )

    def get_context_data(self, **kwargs):

        context = super().get_context_data(**kwargs)
        
        # Проверяем активность торгов на бэкенде
        now = timezone.now()
        order = self.object
        is_tender_active = False
        
        if order.tender_opening_date and order.tender_ending_date:
            if order.tender_opening_date <= now <= order.tender_ending_date:
                is_tender_active = True

        context['is_tender_active'] = is_tender_active

        if 'form' not in context:
            context['form'] = BidForm(order=order)
            
        return context

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        form = BidForm(request.POST, order=self.object)
        
        if form.is_valid():
            now = timezone.now()

            # Дополнительная проверка на бэкенде: торги еще не закончились?
            if self.object.tender_ending_date and now > self.object.tender_ending_date:
                messages.error(request, "Торги по данному заказу уже завершены.")
                return redirect('orders:order_detail', pk=self.object.pk)

            # Сохраняем ставку
            bid = form.save(commit=False)
            bid.client = request.user
            bid.order = self.object
            bid.save()

            # ЛОГИКА ПРОДЛЕНИЯ:
            # Если задано время продления, устанавливаем новое окончание: текущее время + time_to_end
            if self.object.time_to_end:
                new_ending_date = now + timedelta(minutes=self.object.time_to_end)
                
                # Опционально: продлеваем только если новое время больше текущего окончания
                # (чтобы случайно не сократить время, если до конца еще далеко)
                if not self.object.tender_ending_date or new_ending_date > self.object.tender_ending_date:
                    self.object.tender_ending_date = new_ending_date
                    self.object.save(update_fields=['tender_ending_date'])

            messages.success(request, "Ваша ставка успешно принята!")
            return redirect('orders:order_detail', pk=self.object.pk)
        
        context = self.get_context_data(form=form)
        return self.render_to_response(context)


@login_required
def order_bids_api(request, pk):
    """API-эндпоинт для получения актуальных ставок по заказу"""
    order = get_object_or_404(Order, pk=pk, deleted=False)
    
    # Считаем текущую минимальную ставку
    lowest_bid = order.bids.aggregate(models.Min('amount'))['amount__min']
    
    # Ставка текущего пользователя
    user_bid = order.bids.filter(client=request.user).values_list('amount', flat=True).first()

    return JsonResponse({
        'initial_price': float(order.initial_price) if order.initial_price else None,
        'lowest_bid': float(lowest_bid) if lowest_bid else None,
        'user_bid': float(user_bid) if user_bid else None,
        'currency': order.tender_currency,
    })


class OrderViewSet(viewsets.ModelViewSet):
    queryset = Order.objects.filter(deleted=False).prefetch_related('cargoes')
    serializer_class = OrderSerializer
    permission_classes = [IsAdminUser]