# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.http import HttpResponse, HttpResponseRedirect, Http404
from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.admin.views.decorators import staff_member_required
from django.urls import reverse, reverse_lazy
from django.core.exceptions import ObjectDoesNotExist, PermissionDenied
from django.contrib import messages
from django.views.generic.edit import UpdateView, DeleteView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Subquery, OuterRef

import core
import dashboard
import exams
import roster, roster.utils
from . import forms


@login_required
def portal(request, student_id):
	student = roster.utils.get_student(student_id)
	roster.utils.check_can_view(request, student)
	semester = student.semester

	context = {}
	context['title'] = "%s (%s)" %(student.name, student.semester.name)
	context['student'] = student
	context['semester'] = student.semester
	context['omniscient'] = student.is_taught_by(request.user)
	context['curriculum'] = student.generate_curriculum_rows(
			omniscient = context['omniscient'])
	context['tests'] = exams.models.PracticeExam.objects.filter(
			is_test = True, family = semester.exam_family, due_date__isnull=False)
	context['quizzes'] = exams.models.PracticeExam.objects.filter(
			is_test = False, family = semester.exam_family, due_date__isnull=False)
	return render(request, "dashboard/portal.html", context)

@login_required
def uploads(request, student_id, unit_id):
	student = roster.utils.get_student(student_id)
	roster.utils.check_can_view(request, student)

	if unit_id != "0":
		unit = get_object_or_404(core.models.Unit.objects, id = unit_id)
	else:
		unit = None
	uploads = dashboard.models.UploadedFile.objects.filter(benefactor=student, unit=unit)
	if unit is not None \
			and not student.check_unit_unlocked(unit) \
			and not uploads.exists():
		raise PermissionDenied("This unit is not unlocked yet")

	form = None
	if request.method == "POST":
		form = forms.NewUploadForm(request.POST, request.FILES)
		if form.is_valid():
			new_upload = form.save(commit=False)
			new_upload.unit = unit
			new_upload.benefactor = student
			new_upload.owner = request.user
			new_upload.save()
			messages.success(request, "New file has been uploaded.")
			form = None # clear form on successful upload, prevent duplicates
	if form is None:
		form = forms.NewUploadForm(initial = {'unit' : unit})

	context = {}
	context['title'] = 'File Uploads'
	context['student'] = student
	context['unit'] = unit
	context['form'] = form
	context['files'] = uploads
	# TODO form for adding new files
	return render(request, "dashboard/uploads.html", context)

@login_required
def index(request):
	students = roster.utils.get_visible_students(
			request.user, current=True)
	if len(students) == 1: # unique match
		return HttpResponseRedirect(\
				reverse("portal", args=(students[0].id,)))

	context = {}
	context['title'] = "Current Semester Listing"
	context['students'] = students
	context['stulist_show_semester'] = False
	return render(request, "dashboard/stulist.html", context)

@login_required
def past(request):
	students = roster.utils.get_visible_students(
			request.user, current=False)
	context = {}
	context['title'] = "Previous Semester Listing"
	context['students'] = students
	context['stulist_show_semester'] = True
	return render(request, "dashboard/stulist.html", context)

class UpdateFile(LoginRequiredMixin, UpdateView):
	model = dashboard.models.UploadedFile
	fields = ('category', 'content', 'description',)

	def get_success_url(self):
		stu_id = self.object.benefactor.id
		unit_id = self.object.unit.id if self.object.unit is not None else 0
		return reverse("uploads", args=(stu_id, unit_id,))

	def get_object(self, *args, **kwargs):
		obj = super(UpdateFile, self).get_object(*args, **kwargs)
		if not obj.owner == self.request.user \
				and not self.request.user.is_staff:
			raise PermissionDenied("Not authorized to update this file")
		return obj

class DeleteFile(LoginRequiredMixin, DeleteView):
	model = dashboard.models.UploadedFile
	success_url = reverse_lazy("index")

	def get_object(self, *args, **kwargs):
		obj = super(DeleteFile, self).get_object(*args, **kwargs)
		if not obj.owner == self.request.user \
				and not self.request.user.is_staff:
			raise PermissionDenied("Not authorized to delete this file")
		return obj

@staff_member_required
def quasigrader(request, num_limit = 10):
	context = {}
	context['title'] = 'Quasi-grader'
	num_limit = int(num_limit)

	context['items'] = []
	uploads = dashboard.models.UploadedFile.objects\
			.filter(category='psets').order_by('-created_at')[:num_limit]
	for upload in uploads:
		d = {'student' : upload.benefactor,
				'file' : upload,
				'rows' : upload.benefactor.generate_curriculum_rows(True)
				}
		context['items'].append(d)

	context['inquiry_nag'] = roster.models.UnitInquiry.objects\
			.filter(status='NEW').count()

	return render(request, "dashboard/quasigrader.html", context)

@staff_member_required
def idlewarn(request):
	context = {}
	context['title'] = 'Idle-warn'

	newest = dashboard.models.UploadedFile.objects\
			.filter(category='psets')\
			.filter(benefactor=OuterRef('pk'))\
			.order_by('-created_at')\
			.values('created_at')[:1]

	context['students'] = roster.utils\
			.get_visible_students(request.user)\
			.filter(legit=True)\
			.annotate(latest_pset=Subquery(newest))\
			.order_by('latest_pset')

	return render(request, "dashboard/idlewarn.html", context)

@staff_member_required
def leaderboard(request):
	context = {}
	context['title'] = 'Leader-board'

	context['students'] = roster.utils\
			.get_visible_students(request.user)\
			.filter(legit=True)\
			.order_by('-num_units_done')

	return render(request, "dashboard/stulist.html", context)
