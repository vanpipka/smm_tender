from django.contrib.auth.decorators import login_required
from django.utils.decorators import method_decorator
from django.core.files.base import ContentFile
from django.db.models import Min, OuterRef, Subquery
from django.db import models
from django.contrib import messages
from django.utils import timezone
from django.utils.dateparse import parse_datetime, parse_date
from django.views.generic import ListView, DetailView
from django.http import JsonResponse
from datetime import timedelta
import uuid
from django.shortcuts import get_object_or_404, redirect
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import viewsets, generics, status
from rest_framework.permissions import IsAdminUser
from rest_framework.decorators import api_view, permission_classes
from .serializers import OrderFileSerializer, OrderSerializer
from .models import Order, Bid, OrderFile
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
        ).prefetch_related('files', 'cargoes')
    
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


@api_view(['GET'])
@permission_classes([IsAdminUser]) # Доступ только для авторизованных админов (is_staff=True)
def admin_bids_list(request):
    # Получаем параметр date_from из GET-запроса (например: /api/bids/?date_from=2026-06-01T00:00:00)
    date_from_str = request.GET.get('date_from')
    
    bids = Bid.objects.select_related('client', 'order').all()

    if date_from_str:
        # Пытаемся распарсить как дату со временем или просто дату
        parsed_date = parse_datetime(date_from_str)
        if not parsed_date:
            parsed_date = parse_date(date_from_str)
            
        if parsed_date:
            # Фильтруем ставки, созданные начиная с указанной даты
            bids = bids.filter(created_at__gte=parsed_date)
        else:
            return Response(
                {"error": "Неверный формат даты. Используйте YYYY-MM-DD или YYYY-MM-DDTHH:MM:SS"}, 
                status=400
            )

    # Ручная сериализация данных в список словарей для JSON
    data = [
        {
            "id": bid.id,
            "client": bid.client.id,
            "order_id": bid.order.id,
            "amount": str(bid.amount), # DecimalField безопаснее переводить в строку для JSON
            "created_at": bid.created_at.isoformat(),
        }
        for bid in bids
    ]

    return Response(data)


class OrderViewSet(viewsets.ModelViewSet):
    queryset = Order.objects.filter(deleted=False).prefetch_related('cargoes')
    serializer_class = OrderSerializer
    permission_classes = [IsAdminUser]


class OrderFileListCreateView(generics.ListCreateAPIView):
    serializer_class = OrderFileSerializer
    permission_classes = [IsAdminUser] # Или ваши права доступа (например, IsAdminUser)
    http_method_names = ['get']

    def get_queryset(self):
        # Возвращаем файлы только для конкретного заказа из URL
        order_id = self.kwargs.get('pk')
        return OrderFile.objects.filter(order_id=order_id)


class RawFileUploadView(APIView):
    permission_classes = [IsAdminUser]

    def post(self, request, pk):
        order = get_object_or_404(Order, pk=pk)
        
        # Получаем бинарные данные из тела запроса (raw body)
        file_bytes = request.body
        if not file_bytes:
            return Response({"error": "Тело запроса пустое (нет бинарных данных)"}, status=status.HTTP_400_BAD_REQUEST)
        
        # Определяем расширение файла на основе Content-Type
        content_type = request.META.get('CONTENT_TYPE', '').lower()
        
        mime_mapping = {
            'pdf': 'pdf',
            'png': 'png',
            'jpeg': 'jpg',
            'jpg': 'jpg',
            'sheet': 'xlsx',      # Для формата .xlsx (application/vnd.openxmlformats-officedocument.spreadsheetml.sheet)
            'excel': 'xls',       # Для формата .xls (application/vnd.ms-excel)
            'ms-excel': 'xls',    # Дополнительный вариант для .xls
            'csv': 'csv',         # Если вдруг прилетит CSV
            'zip': 'zip',         # Для zip-архивов
            'txt': 'txt',         # Для текстовых файлов
            'json': 'json',       # Для JSON-файлов
            'xml': 'xml',         # Для XML-файлов
            'doc': 'doc',         # Для старых Word-документов
            'docx': 'docx',       # Для новых Word-документов
        }

        # Ищем совпадение по ключевому слову в content_type
        ext = 'bin' # Универсальный fallback по умолчанию
        for keyword, extension in mime_mapping.items():
            if keyword in content_type:
                ext = extension
                break
            
        # Генерируем уникальное имя файла
        filename = f"order_{order.number}_{uuid.uuid4().hex[:8]}.{ext}"
        
        # Создаем запись в базе и сохраняем бинарный контент через ContentFile
        order_file = OrderFile(order=order, name=filename)
        order_file.file.save(filename, ContentFile(file_bytes), save=True)
        
        # Возвращаем результат
        serializer = OrderFileSerializer(order_file)
        return Response(serializer.data, status=status.HTTP_201_CREATED)