from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.permissions import IsAdmin
from apps.dashboard.services import AdminDashboardService
from apps.dashboard.serializers import AdminDashboardOverviewSerializer


from apps.accounts.permissions import IsCustomer
from apps.dashboard.serializers import CustomerDashboardOverviewSerializer
from apps.dashboard.services import CustomerDashboardService

from apps.payments.models import Refund
from apps.dashboard.serializers import CustomerRefundSerializer


class CustomerDashboardOverviewView(APIView):
    permission_classes = [IsAuthenticated, IsCustomer]

    def get(self, request):
        data = CustomerDashboardService.get_overview(request.user)

        serializer = CustomerDashboardOverviewSerializer(data)

        return Response(serializer.data)
    
class CustomerRefundListView(APIView):
    permission_classes = [IsAuthenticated, IsCustomer]

    def get(self, request):
        refunds = (
            Refund.objects
            .filter(payment__order__user=request.user)
            .select_related("payment", "payment__order")
            .order_by("-created_at")
        )

        serializer = CustomerRefundSerializer(
            refunds,
            many=True
        )

        return Response(serializer.data)
    
class AdminDashboardOverviewView(APIView):
    permission_classes = [IsAuthenticated, IsAdmin]

    def get(self, request):
        data = AdminDashboardService.get_overview()

        serializer = AdminDashboardOverviewSerializer(data)

        return Response(serializer.data)