from django.shortcuts import get_object_or_404
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework import status
from .models import Resume, ResumeTemplate, UserTemplate, UserSelectedTemplate
from .serializers import ResumeSerializer, ResumeTemplateSerializer, UserTemplateSerializer
from rest_framework.authentication import SessionAuthentication

class CsrfExemptSessionAuthentication(SessionAuthentication):
    def enforce_csrf(self, request):
        return

class SaveResumeView(APIView):
    permission_classes = [IsAuthenticated]
    authentication_classes = (CsrfExemptSessionAuthentication,)

    def post(self, request, *args, **kwargs):
        serializer = ResumeSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save(user=request.user)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class MyResumesView(APIView):
    permission_classes = [IsAuthenticated]
    authentication_classes = (CsrfExemptSessionAuthentication,)

    def get(self, request, *args, **kwargs):
        resumes = Resume.objects.filter(user=request.user).order_by('-created_at')
        serializer = ResumeSerializer(resumes, many=True)
        return Response(serializer.data)

class CurrentUserView(APIView):
    permission_classes = [IsAuthenticated]
    authentication_classes = (CsrfExemptSessionAuthentication,)

    def get(self, request, *args, **kwargs):
        return Response({"username": request.user.username})

class TemplateListView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = (CsrfExemptSessionAuthentication,)

    def get(self, request, *args, **kwargs):
        templates = ResumeTemplate.objects.filter(is_public=True).order_by('id')
        serializer = ResumeTemplateSerializer(templates, many=True)
        return Response(serializer.data)

class SaveTemplateView(APIView):
    permission_classes = [IsAuthenticated]
    authentication_classes = (CsrfExemptSessionAuthentication,)

    def post(self, request, id, *args, **kwargs):
        try:
            template = ResumeTemplate.objects.get(id=id, is_public=True)
        except ResumeTemplate.DoesNotExist:
            return Response({"error": "Template not found"}, status=status.HTTP_404_NOT_FOUND)
        
        user_template, created = UserTemplate.objects.get_or_create(user=request.user, template=template)
        serializer = UserTemplateSerializer(user_template)
        if created:
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.data, status=status.HTTP_200_OK)

class MyTemplatesView(APIView):
    permission_classes = [IsAuthenticated]
    authentication_classes = (CsrfExemptSessionAuthentication,)

    def get(self, request, *args, **kwargs):
        user_templates = UserTemplate.objects.filter(user=request.user).order_by('-saved_at')
        serializer = UserTemplateSerializer(user_templates, many=True)
        return Response(serializer.data)

class FavoriteTemplateView(APIView):
    permission_classes = [IsAuthenticated]
    authentication_classes = (CsrfExemptSessionAuthentication,)

    def post(self, request, id, *args, **kwargs):
        try:
            template = ResumeTemplate.objects.get(id=id)
        except ResumeTemplate.DoesNotExist:
            return Response({"error": "Template not found"}, status=status.HTTP_404_NOT_FOUND)
        
        user_template, created = UserTemplate.objects.get_or_create(user=request.user, template=template)
        if created:
            user_template.favorite = True
        else:
            user_template.favorite = not user_template.favorite
        user_template.save()
        
        serializer = UserTemplateSerializer(user_template)
        return Response(serializer.data, status=status.HTTP_200_OK)

class UserSelectedTemplateView(APIView):
    permission_classes = [IsAuthenticated]
    authentication_classes = (CsrfExemptSessionAuthentication,)

    def get(self, request, *args, **kwargs):
        try:
            selected = UserSelectedTemplate.objects.get(user=request.user)
            serializer = ResumeTemplateSerializer(selected.template)
            return Response(serializer.data, status=status.HTTP_200_OK)
        except UserSelectedTemplate.DoesNotExist:
            return Response({"error": "No template selected yet"}, status=status.HTTP_404_NOT_FOUND)

    def post(self, request, *args, **kwargs):
        template_id = request.data.get('template_id')
        if not template_id:
            return Response({"error": "template_id is required"}, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            template = ResumeTemplate.objects.get(id=template_id)
        except ResumeTemplate.DoesNotExist:
            return Response({"error": "Template not found"}, status=status.HTTP_404_NOT_FOUND)

        selected_template, created = UserSelectedTemplate.objects.update_or_create(
            user=request.user,
            defaults={'template': template}
        )
        serializer = ResumeTemplateSerializer(template)
        return Response(serializer.data, status=status.HTTP_200_OK)


