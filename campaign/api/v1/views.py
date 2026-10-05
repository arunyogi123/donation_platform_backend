from campaign.models import Campaign, SubscriptionPlan, CampaignDocument
from rest_framework.response import Response
from rest_framework.decorators import api_view
from rest_framework import status
from drf_spectacular.utils import extend_schema
from rest_framework.decorators import permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.permissions import IsAdminUser
from rest_framework.generics import GenericAPIView
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from donations.permission import IsOwnerOrAdmin
from django.shortcuts import get_object_or_404
from rest_framework.generics import ListAPIView
from campaign.api.v1.serialziers import (
    CampaignSerializers,
    SubscriptionSerializers,
    CampaignDocumentSerializer,
)


class CampaignView(GenericAPIView):
    serializer_class = CampaignSerializers
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    @extend_schema(tags=["Campaign"], summary="List approved and active campaigns")
    def get(self, request):
        if request.user.is_authenticated and request.query_params.get("my") == "true":
            campaigns = Campaign.objects.filter(user=request.user).order_by("-id")
        elif request.query_params.get("all") == "true" or (request.user.is_authenticated and request.user.is_staff):
            campaigns = Campaign.objects.all().order_by("-id")
        else:
            campaigns = Campaign.objects.filter(is_approved=True, is_active=True).order_by("-id")
        serializer = CampaignSerializers(campaigns, many=True, context={"request": request})
        return Response(serializer.data)

    @extend_schema(
        request=CampaignSerializers,
        responses=CampaignSerializers,
        summary=" Add new campaign",
        tags=["Campaign"],
    )
    def post(self, request):
        if not (request.user and request.user.is_authenticated):
            return Response(
                {"detail": "Authentication required. Please log in before creating a campaign."},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        # Enforce Creator Profile & Required Verification Documents
        profile = getattr(request.user, "profile", None)
        if not profile or not profile.is_creator_ready:
            missing = profile.get_missing_creator_requirements() if profile else ["Creator profile"]
            return Response(
                {
                    "detail": "Please complete your creator profile and upload all required documents before creating a campaign.",
                    "missing_requirements": missing,
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Enforce Campaign Cover Photograph
        if not request.FILES.get("image") and not request.data.get("image") and not request.data.get("image_url"):
            return Response(
                {
                    "detail": "Please upload a campaign cover photograph.",
                    "image": ["Campaign cover photograph is required."],
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Enforce Campaign Case Supporting Document (Mandatory)
        document_file = request.FILES.get("document") or request.FILES.get("document_file")
        doc_files = request.FILES.getlist("documents")
        if not document_file and not doc_files:
            return Response(
                {
                    "detail": "Please upload at least one supporting document for this campaign.",
                    "document": ["At least one campaign case supporting document is required."],
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        data = request.data
        serializer = CampaignSerializers(data=data, context={"request": request})
        if serializer.is_valid():
            extra_kwargs = {"user": request.user}
            if not serializer.validated_data.get("organizer_name"):
                extra_kwargs["organizer_name"] = profile.full_name or request.user.get_full_name() or request.user.username
            campaign = serializer.save(**extra_kwargs)

            # Support uploading essential document alongside campaign creation in a single multipart request
            doc_type = request.data.get("document_type", "medical")
            if document_file:
                doc_serializer = CampaignDocumentSerializer(
                    data={"document": document_file, "document_type": doc_type},
                    context={"request": request}
                )
                if doc_serializer.is_valid():
                    doc_serializer.save(campaign=campaign)


            doc_files = request.FILES.getlist("documents")
            for f in doc_files:
                d_ser = CampaignDocumentSerializer(
                    data={"document": f, "document_type": doc_type},
                    context={"request": request}
                )
                if d_ser.is_valid():
                    d_ser.save(campaign=campaign)

            response_serializer = CampaignSerializers(campaign, context={"request": request})
            return Response(
                {"message": "Successfully added", "data": response_serializer.data},
                status=status.HTTP_201_CREATED,
            )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)



class CampaignDetailView(GenericAPIView):
    serializer_class = CampaignSerializers
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    @extend_schema(tags=["Campaign"], summary="Get campaign by ID")
    def get(self, request, id):
        campaign = get_object_or_404(Campaign, id=id)
        serializer = CampaignSerializers(campaign, context={"request": request})
        return Response(serializer.data)



@extend_schema(
    request=CampaignSerializers,
    responses=CampaignSerializers,
    summary="Delete campaign list ",
    tags=["Campaign"],
)
class CampaignDelete(GenericAPIView):
    queryset = Campaign.objects.all()
    serializer_class = [CampaignSerializers]
    permission_classes = [IsAuthenticated, IsOwnerOrAdmin]
    

    def delete(self, request, id):
        plan = Campaign.objects.get(id=id)
        self.check_object_permissions(request, plan)
        plan.delete()
        return Response({"message": "Successfully deleted"}, status.HTTP_204_NO_CONTENT)


@extend_schema(
    request=CampaignSerializers,
    responses=CampaignSerializers,
    summary="Update campaign list ",
    tags=["Campaign"],
)
class CampaigUpdate(GenericAPIView):
    queryset = Campaign.objects.all()
    serializer_class = CampaignSerializers
    permission_classes = [IsAuthenticated, IsOwnerOrAdmin]

    def put(self, request, id):
        campaign = get_object_or_404(Campaign, id=id)

        # checks owner OR admin
        self.check_object_permissions(request, campaign)

        serializer = CampaignSerializers(
            campaign,
            data=request.data,
            partial=True
        )

        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)

        return Response(serializer.errors, status=400)


class SubscriptionView(GenericAPIView):
    queryset = SubscriptionPlan.objects.all()
    serializer_class = [SubscriptionSerializers]

    @extend_schema(
        responses=SubscriptionSerializers,
        summary="Get subscription details",
        tags=["Subscription"],
    )
    def get(self, request):
        plan = SubscriptionPlan.objects.all()
        serializer = SubscriptionSerializers(plan, many=True)
        return Response(serializer.data)

    @extend_schema(
        request=SubscriptionSerializers,
        responses=SubscriptionSerializers,
        summary=" Add new subscription",
        tags=["Subscription"],
    )
    def post(self, request):
        data = request.data
        serializer = SubscriptionSerializers(data=data)

        if serializer.is_valid():
            serializer.save()
            return Response(
                {"message": "Successfully added", "data": serializer.data},
                status=status.HTTP_201_CREATED,
            )

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@extend_schema(
    responses=SubscriptionSerializers,
    request=SubscriptionSerializers,
    summary="Update subscription details",
    tags=["Subscription"],
    description="Update Subscription plan instance",
)
@api_view(["PUT"])
@permission_classes([IsAuthenticated])
def update_subscription(request, id):
    data = request.data
    plan = SubscriptionPlan.objects.get(id=id)
    serializer = SubscriptionSerializers(data=data, instance=plan)
    if serializer.is_valid():
        serializer.save()
        return Response(
            {"message": "Successfully Updated", "data": serializer.data},
            status.HTTP_200_OK,
        )
    return Response(serializer.errors, status.HTTP_400_BAD_REQUEST)


@extend_schema(
    request=SubscriptionSerializers,
    responses=SubscriptionSerializers,
    summary="Delete subscription ",
    tags=["Subscription"],
)
class SubscrptionDelete(GenericAPIView):
    queryset = SubscriptionPlan.objects.all()
    serializer_class = [SubscriptionSerializers]

    def delete(self, request, id):
        data = SubscriptionPlan.objects.get(id=id)
        data.delete()
        return Response({"message": "Successfully deleted"}, status.HTTP_204_NO_CONTENT)




class DocumentView(GenericAPIView):
    queryset = CampaignDocument.objects.all()
    serializer_class = CampaignDocumentSerializer
    parser_classes = [MultiPartParser, FormParser, JSONParser]
    permission_classes = []

    @extend_schema(
        request=CampaignDocumentSerializer,
        responses=CampaignDocumentSerializer,
        tags=['documents']
    )
    def get(self, request, campaign):
        campaign_obj = get_object_or_404(Campaign, id=campaign)
        docs = CampaignDocument.objects.filter(campaign=campaign_obj).order_by("-uploaded_at")
        serializer = self.get_serializer(
            docs, many=True,
            context={"request": request}
        )
        return Response(serializer.data)
    
    @extend_schema(
        request=CampaignDocumentSerializer,
        responses=CampaignDocumentSerializer,
        tags=['documents']
    )
    def post(self, request, campaign):
        if not (request.user and request.user.is_authenticated):
            return Response(
                {"detail": "Authentication required to upload documents."},
                status=status.HTTP_401_UNAUTHORIZED
            )
        campaign_obj = get_object_or_404(Campaign, id=campaign)
        # Verify ownership: Only staff or creator of campaign can add documents
        if not (request.user.is_staff or campaign_obj.user == request.user or campaign_obj.user is None):
            return Response(
                {"detail": "You do not have permission to upload documents for this campaign."},
                status=status.HTTP_403_FORBIDDEN
            )

        serializer = self.get_serializer(
            data=request.data,
            context={"request": request}
        )

        if serializer.is_valid():
            serializer.save(campaign=campaign_obj)
            return Response(serializer.data, status=status.HTTP_201_CREATED)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class DocumentManage(GenericAPIView):
    queryset = CampaignDocument.objects.all()
    serializer_class = CampaignDocumentSerializer
    parser_classes = [MultiPartParser, FormParser, JSONParser]
    permission_classes = [IsAuthenticated, IsOwnerOrAdmin]
    
    @extend_schema(
        responses=CampaignDocumentSerializer,
        request=CampaignDocumentSerializer,
        tags=['documents']
    )
    def put(self, request, id):
        doc = get_object_or_404(CampaignDocument, id=id)
        self.check_object_permissions(request, doc)

        serializer = self.get_serializer(
            doc,
            data=request.data,
            partial=True,
            context={"request": request}
        )

        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    @extend_schema(
        request=CampaignDocumentSerializer,
        responses=CampaignDocumentSerializer,
        tags=['documents']
    )
    def delete(self, request, id):
        doc = get_object_or_404(CampaignDocument, id=id)
        self.check_object_permissions(request, doc)
        
        doc.delete()
        return Response(
            {"message": "Successfully deleted"},
            status=status.HTTP_200_OK
        )