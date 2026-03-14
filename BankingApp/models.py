from django.db import models
from django.core.validators import MinValueValidator
from decimal import Decimal
from django.utils import timezone
from django.conf import settings

# Create your models here.
class Banking(models.Model):
    CATEGORY_CHOICES = [
        ('savings', 'Savings'),
        ('out', 'Outing'),
        ('purchase', 'Business'),
        ('investment', 'Investment'),
        ('miscellaneous', 'Miscellaneous'),
        ('emergency', 'Emergency Fund'),
    ]

    bank_name = models.CharField(max_length=200)
    bank_description = models.TextField(blank=True)
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES, default='savings')
    target_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))],
        null=True,
        blank = True,
        help_text="Target amount for this bank account"
    )
    minimum_amount = models.DecimalField(
        max_digits= 12,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))],
        null = True,
        blank = True,
        help_text = "Minimum Amount before alert"
    )

    is_active = models.BooleanField(
        default=True,
        help_text="Only active banks are included in analysis and calculations"
    )
    user_id = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return self.bank_name

    @property
    def current_balance(self):
        """Calculate current balance from all transactions"""
        deposits = self.transactions.filter(transaction_type='deposit').aggregate(
            total=models.Sum('amount'))['total'] or Decimal('0.00')
        withdrawals = self.transactions.filter(transaction_type='withdraw').aggregate(
            total=models.Sum('amount'))['total'] or Decimal('0.00')
        charges = self.transactions.filter(transaction_type='charges').aggregate(
            total=models.Sum('amount'))['total'] or Decimal('0.00')
        interest = self.transactions.filter(transaction_type='interest').aggregate(
            total=models.Sum('amount'))['total'] or Decimal('0.00')
        loan = self.transactions.filter(transaction_type='loan').aggregate(
            total=models.Sum('amount'))['total'] or Decimal('0.00')
        return (deposits + interest) - (withdrawals + charges + loan)

    @property
    def progress_percentage(self):
        """Calculate progress towards target amount"""
        if not self.target_amount  or self.target_amount <= 0:
            return 0.0
        return float(min(100, (self.current_balance / self.target_amount) * 100))
    @property
    def minimumAlert(self):
        if self.minimum_amount and self.current_balance < self.minimum_amount:
            return True
        return False


class Transaction(models.Model):
    TRANSACTION_TYPES = [
        ('deposit', 'Deposit'),
        ('withdraw', 'Withdraw'),
        ('charges', 'Bank Charges'),
        ('interest', 'Interest'),
        ('loan', 'Loan'),

    ]

    banking = models.ForeignKey(Banking, on_delete=models.CASCADE, related_name='transactions')
    transaction_type = models.CharField(max_length=10, choices=TRANSACTION_TYPES)
    amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))]
    )
    description = models.CharField(max_length=200, blank=True)
    user_id = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    transaction_date = models.DateTimeField(default=timezone.now)
    created_at = models.DateTimeField(auto_now_add=True)


    class Meta:
        ordering = ['-transaction_date']

    def __str__(self):
        return f"{self.get_transaction_type_display()} - ${self.amount} - {self.banking.bank_name}"
