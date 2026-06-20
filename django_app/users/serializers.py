from rest_framework import serializers
from .models import Resume, ResumeTemplate, UserTemplate

class ResumeSerializer(serializers.ModelSerializer):
    class Meta:
        model = Resume
        fields = '__all__'
        read_only_fields = ('user',)

class ResumeTemplateSerializer(serializers.ModelSerializer):
    class Meta:
        model = ResumeTemplate
        fields = '__all__'

class UserTemplateSerializer(serializers.ModelSerializer):
    template_details = ResumeTemplateSerializer(source='template', read_only=True)

    class Meta:
        model = UserTemplate
        fields = ['id', 'user', 'template', 'saved_at', 'favorite', 'template_details']
        read_only_fields = ('user', 'saved_at')

