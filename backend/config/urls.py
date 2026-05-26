from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView
from rest_framework_simplejwt.views import TokenRefreshView

from core.views import LegacyLoginView, LegacyVerifyOTPView, LoginView


urlpatterns = [
    path("admin/", admin.site.urls),
    path("AccountLogin/Login", LegacyLoginView.as_view(), name="legacy-account-login"),
    path("AccountLogin/Login/", LegacyLoginView.as_view(), name="legacy-account-login-slash"),
    path("AccountLogin/VerifyOTP", LegacyVerifyOTPView.as_view(), name="legacy-account-verify-otp"),
    path("AccountLogin/VerifyOTP/", LegacyVerifyOTPView.as_view(), name="legacy-account-verify-otp-slash"),
    path("api/auth/login/", LoginView.as_view(), name="token_obtain_pair"),
    path("api/auth/refresh/", TokenRefreshView.as_view(), name="token_refresh"),
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path("api/docs/", SpectacularSwaggerView.as_view(url_name="schema"), name="swagger-ui"),
    path("api/", include("core.urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
