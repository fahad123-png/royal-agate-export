from django.shortcuts import get_object_or_404
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework import status
from rest_framework.generics import ListAPIView, RetrieveAPIView

from django.db.models import Q
from rest_framework.pagination import PageNumberPagination
from rest_framework.exceptions import ValidationError

from apps.accounts.permissions import IsCustomer, IsAdmin

from .models import Order, OrderCancellation, OrderStatusHistory
from .serializers import (
    OrderCreateSerializer,
    OrderCreateResponseSerializer,
    OrderSerializer,
    CancellationRequestSerializer,
    CancellationReviewSerializer,
    OrderCancellationSerializer,
    OrderStatusUpdateSerializer,
    OrderStatusHistorySerializer,
    AdminOrderSerializer,
)
from .services import OrderService


class OrderCreateView(APIView):

    permission_classes = [IsAuthenticated, IsCustomer]

    def post(self, request):

        request_serializer = OrderCreateSerializer(
            data=request.data
        )
        request_serializer.is_valid(raise_exception=True)

        order = OrderService.create_order(
            user=request.user,
            address_id=request_serializer.validated_data["address_id"],
            notes=request_serializer.validated_data.get("notes", "")
        )

        response_data = {
            "message": "Order created successfully.",
            "order": order,
        }

        response_serializer = OrderCreateResponseSerializer(
            response_data
        )

        return Response(
            response_serializer.data,
            status=status.HTTP_201_CREATED
        )


class OrderListView(ListAPIView):

    serializer_class = OrderSerializer

    permission_classes = [IsAuthenticated, IsCustomer]

    def get_queryset(self):

        return (
            Order.objects
            .filter(user=self.request.user)
            .prefetch_related("items")
        )


class OrderDetailView(RetrieveAPIView):

    serializer_class = OrderSerializer

    permission_classes = [IsAuthenticated, IsCustomer]

    lookup_field = "pk"

    def get_queryset(self):

        return (
            Order.objects
            .filter(user=self.request.user)
            .prefetch_related("items")
        )
        
class CustomerOrderCancelView(APIView):

    permission_classes = [IsAuthenticated, IsCustomer]

    def post(self, request, pk):

        serializer = CancellationRequestSerializer(
            data=request.data
        )
        serializer.is_valid(raise_exception=True)

        cancellation = OrderService.request_cancellation(
            user=request.user,
            order_id=pk,
            reason=serializer.validated_data["reason"]
        )

        if cancellation.status == OrderCancellation.CancellationStatus.DIRECT_CANCELLED:
            message = "Order cancelled successfully."
        else:
            message = "Cancellation request submitted successfully."

        return Response(
            {
                "message": message,
                "cancellation": OrderCancellationSerializer(cancellation).data
            },
            status=status.HTTP_201_CREATED
        )


class AdminOrderConfirmView(APIView):

    permission_classes = [IsAuthenticated, IsAdmin]

    def post(self, request, pk):

        order = OrderService.confirm_order(
            order_id=pk,
            admin_user=request.user
        )

        return Response(
            {
                "message": "Order confirmed successfully.",
                "order": OrderSerializer(order).data
            },
            status=status.HTTP_200_OK
        )
        
class CustomerCancellationListView(ListAPIView):

    serializer_class = OrderCancellationSerializer

    permission_classes = [IsAuthenticated, IsCustomer]

    def get_queryset(self):

        return (
            OrderCancellation.objects
            .filter(requested_by=self.request.user)
            .select_related("order", "requested_by", "reviewed_by")
        )
        
class AdminCancellationListView(ListAPIView):

    serializer_class = OrderCancellationSerializer

    permission_classes = [IsAuthenticated, IsAdmin]

    def get_queryset(self):

        queryset = (
            OrderCancellation.objects
            .select_related("order", "requested_by", "reviewed_by")
        )

        cancellation_status = self.request.query_params.get("status")

        if cancellation_status:
            queryset = queryset.filter(status=cancellation_status.upper())

        return queryset
    
class AdminCancellationApproveView(APIView):

    permission_classes = [IsAuthenticated, IsAdmin]

    def post(self, request, pk):

        serializer = CancellationReviewSerializer(
            data=request.data
        )
        serializer.is_valid(raise_exception=True)

        cancellation = OrderService.approve_cancellation(
            cancellation_id=pk,
            admin_user=request.user,
            admin_note=serializer.validated_data.get("admin_note", "")
        )

        return Response(
            {
                "message": "Cancellation request approved successfully.",
                "cancellation": OrderCancellationSerializer(cancellation).data
            },
            status=status.HTTP_200_OK
        )
        
class AdminCancellationRejectView(APIView):

    permission_classes = [IsAuthenticated, IsAdmin]

    def post(self, request, pk):

        serializer = CancellationReviewSerializer(
            data=request.data
        )
        serializer.is_valid(raise_exception=True)

        cancellation = OrderService.reject_cancellation(
            cancellation_id=pk,
            admin_user=request.user,
            admin_note=serializer.validated_data.get("admin_note", "")
        )

        return Response(
            {
                "message": "Cancellation request rejected successfully.",
                "cancellation": OrderCancellationSerializer(cancellation).data
            },
            status=status.HTTP_200_OK
        )
        
class AdminOrderStatusUpdateView(APIView):

    permission_classes = [IsAuthenticated, IsAdmin]

    def post(self, request, pk):

        serializer = OrderStatusUpdateSerializer(
            data=request.data
        )

        serializer.is_valid(raise_exception=True)

        order = OrderService.update_order_status(
            order_id=pk,
            new_status=serializer.validated_data["status"],
            admin_user=request.user,
            note=serializer.validated_data.get("note", "")
        )

        return Response(
            {
                "message": "Order status updated successfully.",
                "order": OrderSerializer(order).data
            },
            status=status.HTTP_200_OK
        )
        
class CustomerOrderTimelineView(ListAPIView):

    serializer_class = OrderStatusHistorySerializer

    permission_classes = [IsAuthenticated, IsCustomer]

    def get_queryset(self):

        order = get_object_or_404(
            Order,
            pk=self.kwargs["pk"],
            user=self.request.user
        )

        return (
            OrderStatusHistory.objects
            .filter(order=order)
            .select_related("changed_by")
            .order_by("created_at", "id")
        )
        
class AdminOrderPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = "page_size"
    max_page_size = 100


class AdminOrderListView(ListAPIView):
    serializer_class = AdminOrderSerializer
    permission_classes = [IsAuthenticated, IsAdmin]
    pagination_class = AdminOrderPagination

    def get_queryset(self):

        queryset = (
            Order.objects
            .select_related("user")
            .prefetch_related("items")
            .order_by("-created_at")
        )

        # Order status filter
        order_status = self.request.query_params.get("status")

        if order_status:
            order_status = order_status.upper()

            if order_status not in Order.OrderStatus.values:
                raise ValidationError({
                    "status": "Invalid order status."
                })

            queryset = queryset.filter(status=order_status)

        # Payment status filter
        payment_status = self.request.query_params.get(
            "payment_status"
        )

        if payment_status:
            payment_status = payment_status.upper()

            if payment_status not in Order.PaymentStatus.values:
                raise ValidationError({
                    "payment_status": "Invalid payment status."
                })

            queryset = queryset.filter(
                payment_status=payment_status
            )

        # Search
        search = self.request.query_params.get("search", "").strip()

        if search:
            queryset = queryset.filter(
                Q(order_number__icontains=search)
                | Q(shipping_full_name__icontains=search)
                | Q(user__email__icontains=search)
                | Q(user__first_name__icontains=search)
                | Q(user__last_name__icontains=search)
            )

        return queryset


class AdminOrderDetailView(RetrieveAPIView):
    serializer_class = AdminOrderSerializer
    permission_classes = [IsAuthenticated, IsAdmin]

    def get_queryset(self):
        return (
            Order.objects
            .select_related("user")
            .prefetch_related("items")
        )