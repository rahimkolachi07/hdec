from django.contrib import admin
from django.urls import path
from maintenance import views as mv

urlpatterns = [
    path('admin/', admin.site.urls),
    path('',              mv.overview,         name='overview'),
    path('pm/',           mv.pm_page,           name='pm'),
    path('cm/',           mv.cm_page,           name='cm'),
    path('trackers/',     mv.trackers_page,     name='trackers'),
    path('strings/',      mv.strings_page,      name='strings'),
    path('equipment/',    mv.equipment_page,    name='equipment'),
    path('observations/', mv.observations_page, name='observations'),
    path('sync/',         mv.sync_page,         name='sync'),
    path('api/sync-now/',    mv.sync_now,       name='sync_now'),
    path('api/sync-status/', mv.sync_status,    name='sync_status'),
    path('api/kpis/',        mv.api_kpis,       name='api_kpis'),
]
