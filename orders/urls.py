from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import OrderListView, OrderDetailView, order_bids_api, OrderViewSet

app_name = 'orders'

router = DefaultRouter()
router.register(r'api/orders', OrderViewSet, basename='order-api')

urlpatterns = [
    # Ваши существующие URL-адреса страниц...
    path('', OrderListView.as_view(), name='order_list'),
    path('<int:pk>/', OrderDetailView.as_view(), name='order_detail'),
    path('api/<int:pk>/bids/', order_bids_api, name='order_bids_api'),
    
    # Подключаем роутер DRF API
    path('', include(router.urls)),
]