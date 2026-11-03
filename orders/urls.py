from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import OrderFileListCreateView, OrderListView, OrderDetailView, RawFileUploadView, order_bids_api, OrderViewSet

app_name = 'orders'

router = DefaultRouter()
router.register(r'api/orders', OrderViewSet, basename='order-api')

urlpatterns = [
    # Ваши существующие URL-адреса страниц...
    path('', OrderListView.as_view(), name='order_list'),
    path('<int:pk>/', OrderDetailView.as_view(), name='order_detail'),
    path('api/<int:pk>/bids/', order_bids_api, name='order_bids_api'),
    
    path('api/orders/<int:pk>/files/upload/', RawFileUploadView.as_view(), name='order-upload-raw'),
    path('api/orders/<int:pk>/files/', OrderFileListCreateView.as_view(), name='order-files'),
    
    # Подключаем роутер DRF API
    path('', include(router.urls)),
]