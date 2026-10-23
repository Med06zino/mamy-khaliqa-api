from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.common.permissions import IsStaffUser

from .models import StoreSettings
from .serializers import AdminStoreSettingsSerializer, PublicStoreSettingsSerializer


class PublicSettingsView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        data = PublicStoreSettingsSerializer(StoreSettings.load(), context={"request": request}).data
        return Response(data)


class AdminSettingsView(APIView):
    permission_classes = [IsStaffUser]

    def get(self, request):
        return Response(AdminStoreSettingsSerializer(StoreSettings.load(), context={"request": request}).data)

    def patch(self, request):
        obj = StoreSettings.load()
        s = AdminStoreSettingsSerializer(obj, data=request.data, partial=True, context={"request": request})
        s.is_valid(raise_exception=True)
        s.save()
        return Response(s.data)
