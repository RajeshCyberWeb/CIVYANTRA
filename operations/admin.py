from django.contrib import admin
from .models import Attendance, Material, ProjectMaterialInventory, MaterialRequest, StockTransaction, SiteProblemReport

admin.site.register(Attendance)
admin.site.register(Material)
admin.site.register(ProjectMaterialInventory)
admin.site.register(MaterialRequest)
admin.site.register(StockTransaction)
admin.site.register(SiteProblemReport)
