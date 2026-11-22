from django.contrib import admin
from .models import Project, ProjectHoliday, ProjectAssignment, Task, TaskProgressHistory, TaskQuantityAdjustment, TaskDelayReport

admin.site.register(Project)
admin.site.register(ProjectHoliday)
admin.site.register(ProjectAssignment)
admin.site.register(Task)
admin.site.register(TaskProgressHistory)
admin.site.register(TaskQuantityAdjustment)
admin.site.register(TaskDelayReport)
