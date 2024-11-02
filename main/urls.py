from django.urls import path
from . import views

urlpatterns = [
    path('',views.home,name='home'),
    path('login/',views.login_view,name='login'),
    path('register/',views.register,name='register'),
    path('logout/', views.logout_view, name='logout'),
    path('join-queue/', views.join_queue, name='join_queue'),
    path('get-realtime-data/', views.get_realtime_data, name='get_realtime_data'),
    path('check_status/', views.check_status, name='check_status'),
    path('download_qr_code/', views.download_qr_code, name='download_qr_code'),
    path('history/', views.history, name='history'),
]