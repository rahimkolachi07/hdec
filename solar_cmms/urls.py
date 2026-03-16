from django.contrib import admin
from django.urls import path
from django.conf import settings
from django.conf.urls.static import static
from maintenance import views as mv
from django.contrib.auth import views as auth_views

urlpatterns = [
    path('admin/',              admin.site.urls),
    path('login/',              mv.login_view,         name='login'),
    path('logout/',             mv.logout_view,        name='logout'),
    path('',                    mv.home,               name='home'),
    path('pm/',                 mv.pm_page,            name='pm'),
    path('cm/',                 mv.cm_page,            name='cm'),
    path('trackers/',           mv.trackers_page,      name='trackers'),
    path('strings/',            mv.strings_page,       name='strings'),
    path('mvps/',               mv.mvps_page,          name='mvps'),
    path('equipment/',          mv.equipment_page,     name='equipment'),
    path('observations/',       mv.observations_page,  name='observations'),
    path('daily-report/',       mv.daily_report,       name='daily_report'),
    path('staff/',              mv.staff_page,         name='staff'),
    path('documents/',          mv.documents_page,     name='documents'),
    path('material/',           mv.material_page,      name='material'),
    path('sync/',               mv.sync_page,          name='sync'),
    path('settings/',           mv.settings_page,      name='settings'),
    # APIs
    path('api/sync-now/',       mv.sync_now,           name='sync_now'),
    path('api/sync-status/',    mv.sync_status,        name='sync_status'),
    path('api/kpis/',           mv.api_kpis,           name='api_kpis'),
    path('api/search/',         mv.search_api,         name='search_api'),
    path('api/chat/',           mv.chat_api,           name='chat_api'),
    path('api/doc-upload/',     mv.doc_upload,         name='doc_upload'),
    path('api/doc-delete/<str:doc_id>/', mv.doc_delete, name='doc_delete'),
    path('api/rag-stats/',      mv.rag_stats_api,      name='rag_stats'),
    path('api/save-settings/',  mv.save_settings,      name='save_settings'),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
