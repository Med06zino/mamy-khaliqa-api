from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.http import HttpResponse
from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView
from rest_framework.routers import DefaultRouter

from apps.accounts import views as acc
from apps.banners import views as banners
from apps.catalog import views as cat
from apps.contact import views as contact
from apps.deliveries import views as deliv
from apps.newsletter import views as newsletter
from apps.orders import views as orders
from apps.payments import urls as payments_urls
from apps.reviews import views as reviews
from apps.store_settings import views as store

# ── Routes publiques ─────────────────────────────────────────────
router = DefaultRouter()
router.register("categories",    cat.CategoryViewSet,     basename="category")
router.register("products",      cat.ProductViewSet,      basename="product")
router.register("addresses",     acc.AddressViewSet,      basename="address")
router.register("favorites",     acc.FavoriteViewSet,     basename="favorite")
router.register("orders",        orders.OrderViewSet,     basename="order")
router.register("delivery-zones",deliv.DeliveryZoneViewSet, basename="delivery-zone")
router.register("reviews",       reviews.ReviewViewSet,   basename="review")
router.register("contact",       contact.ContactViewSet,  basename="contact")
router.register("banners",       banners.BannerViewSet,   basename="banner")

# ── Routes administration ────────────────────────────────────────
admin_router = DefaultRouter()
admin_router.register("products",       cat.AdminProductViewSet,       basename="admin-product")
admin_router.register("variants",       cat.AdminVariantViewSet,       basename="admin-variant")
admin_router.register("categories",     cat.AdminCategoryViewSet,      basename="admin-category")
admin_router.register("orders",         orders.AdminOrderViewSet,      basename="admin-order")
admin_router.register("customers",      acc.AdminCustomerViewSet,      basename="admin-customer")
admin_router.register("delivery-zones", deliv.AdminDeliveryZoneViewSet, basename="admin-delivery-zone")
admin_router.register("reviews",        reviews.AdminReviewViewSet,    basename="admin-review")
admin_router.register("messages",       contact.AdminContactViewSet,   basename="admin-message")
admin_router.register("banners",        banners.AdminBannerViewSet,    basename="admin-banner")
admin_router.register("newsletter",     newsletter.AdminNewsletterViewSet, basename="admin-newsletter")

auth_patterns = [
    path("csrf/",                   acc.CsrfView.as_view()),
    path("register/",               acc.RegisterView.as_view()),
    path("login/",                  acc.LoginView.as_view()),
    path("logout/",                 acc.LogoutView.as_view()),
    path("me/",                     acc.MeView.as_view()),
    path("change-password/",        acc.ChangePasswordView.as_view()),
    path("password-reset/",         acc.PasswordResetView.as_view()),
    path("password-reset/confirm/", acc.PasswordResetConfirmView.as_view()),
]


def sitemap_view(request):
    """Sitemap XML dont les URL pointent vers le site public (FRONTEND_URL)."""
    from apps.catalog.models import Category, Product

    base = settings.FRONTEND_URL.rstrip("/")
    urls = [f"{base}/", f"{base}/boutique", f"{base}/promotions"]
    urls += [f"{base}/boutique/categorie/{c.slug}" for c in Category.objects.filter(is_active=True)]
    urls += [f"{base}/boutique/{p.slug}" for p in Product.objects.public()]
    urls += [f"{base}/{x}" for x in (
        "a-propos", "contact", "faq", "livraison",
        "retours", "conditions-generales", "confidentialite",
    )]
    body = '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
    body += "".join(f"  <url><loc>{u}</loc></url>\n" for u in urls) + "</urlset>\n"
    return HttpResponse(body, content_type="application/xml")


def robots(request):
    body = (
        "User-agent: *\n"
        "Disallow: /admin\n"
        "Disallow: /compte\n"
        "Disallow: /panier\n"
        "Disallow: /commande\n"
        "Disallow: /api/\n"
    )
    return HttpResponse(body, content_type="text/plain")


urlpatterns = [
    path("django-admin/",   admin.site.urls),
    path("api/v1/auth/",    include(auth_patterns)),
    path("api/v1/settings/",store.PublicSettingsView.as_view()),
    path("api/v1/admin/dashboard/", orders.AdminDashboardView.as_view()),
    path("api/v1/admin/settings/",  store.AdminSettingsView.as_view()),
    path("api/v1/admin/",   include(admin_router.urls)),
    path("api/v1/payments/", include(payments_urls)),
    path("api/v1/",         include(router.urls)),
    path("api/v1/newsletter/subscribe/", newsletter.NewsletterSubscribeView.as_view()),
    path("api/schema/",     SpectacularAPIView.as_view(), name="schema"),
    path("api/docs/",       SpectacularSwaggerView.as_view(url_name="schema"), name="swagger"),
    path("sitemap.xml",     sitemap_view),
    path("robots.txt",      robots),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
