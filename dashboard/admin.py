# -*- coding: utf-8 -*-
from __future__ import unicode_literals

import dashboard

from django.contrib import admin

@admin.register(dashboard.models.UploadedFile)
class UploadedFileAdmin(admin.ModelAdmin):
	list_display = ('id', 'content', 'created_at', 'description',
			'benefactor', 'unit', 'category', 'owner',)
	search_fields = ('description',)
	list_per_page = 30
