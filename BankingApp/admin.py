from django.contrib import admin

# Register your models here.
from .models import Banking, Transaction


@admin.register(Banking)
class BankingAdmin(admin.ModelAdmin):
    list_display = ['bank_name', 'category', 'is_active', 'target_amount', 'current_balance', 'progress_percentage',
                    'created_at']
    list_filter = ['category', 'is_active', 'created_at']
    search_fields = ['bank_name', 'bank_description']
    readonly_fields = ['current_balance', 'progress_percentage']
    list_editable = ['is_active']

    def current_balance(self, obj):
        return f"${obj.current_balance:,.2f}"

    current_balance.short_description = 'Current Balance'

    def progress_percentage(self, obj):
        return f"{obj.progress_percentage:.1f}%"

    progress_percentage.short_description = 'Progress'


@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    list_display = ['banking', 'transaction_type', 'amount', 'description', 'transaction_date']
    list_filter = ['transaction_type', 'transaction_date', 'banking']
    search_fields = ['description', 'banking__bank_name']
    date_hierarchy = 'transaction_date'
