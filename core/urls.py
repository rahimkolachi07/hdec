from django.urls import path
from . import views

urlpatterns = [
    path('', views.home, name='home'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('admin-panel/', views.admin_panel, name='admin_panel'),
    path('api/admin/', views.admin_api, name='admin_api'),
    # Manpower
    path('manpower/', views.manpower, name='manpower'),
    path('api/manpower/import/', views.manpower_import, name='manpower_import'),
    path('api/manpower/export/', views.manpower_export, name='manpower_export'),
    # Attendance
    path('api/attendance/face/', views.attendance_face_api, name='attendance_face_api'),
    path('api/attendance/face/delete/', views.attendance_face_delete, name='attendance_face_delete'),
    path('api/attendance/face/descriptors/', views.attendance_face_descriptors, name='attendance_face_descriptors'),
    path('api/attendance/people/', views.attendance_people, name='attendance_people'),
    path('api/attendance/face/photo/save/', views.attendance_face_photo_save, name='attendance_face_photo_save'),
    path('api/attendance/face/photo/all/', views.attendance_face_photos_all, name='attendance_face_photos_all'),
    path('api/attendance/face/photo/<str:name>/', views.attendance_face_photo_get, name='attendance_face_photo_get'),
    path('api/attendance/mark/', views.attendance_mark, name='attendance_mark'),
    path('api/attendance/', views.attendance_get, name='attendance_get'),
    path('api/attendance/export/', views.attendance_export, name='attendance_export'),
    # Tracing
    path('tracing/', views.tracing_hub, name='tracing_hub'),
    path('tracing/<slug:slug>/', views.tracing_sheet, name='tracing_sheet'),
    # Annual Plan
    path('annual-plan/', views.annual_plan, name='annual_plan'),
    path('annual-plan/sheet/<slug:slug>/', views.annual_plan_sheet, name='annual_plan_sheet'),
    path('annual-plan/<slug:slug>/', views.annual_plan_folder, name='annual_plan_folder'),
    # Other pages
    path('documents/', views.documents, name='documents'),
    path('daily-report/', views.daily_report, name='daily_report'),
    # APIs
    path('api/chat/', views.chat_api, name='chat_api'),
    path('api/tracing/<slug:slug>/', views.tracing_sheet_api, name='tracing_sheet_api'),
    path('api/annual-plan/', views.annual_plan_api, name='annual_plan_api'),
    path('api/annual-plan/sheet/<slug:slug>/', views.annual_plan_sheet_api, name='annual_plan_sheet_api'),
    path('api/annual-plan/<slug:slug>/', views.annual_plan_folder_api, name='annual_plan_folder_api'),
]
