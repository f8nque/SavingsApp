from django.shortcuts import render

# Create your views here.
from django.shortcuts import render, get_object_or_404, redirect
from django.views import View
from django.contrib import messages
from django.db.models import Sum, Q
from django.utils import timezone
from datetime import datetime, timedelta
from .models import Banking, Transaction
from .forms import TransactionForm
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.models import User






class DashboardView(LoginRequiredMixin,View):
    def get(self,request):
        """Dashboard showing banking activity for the last 3 months - only active banks"""
        three_months_ago = timezone.now() - timedelta(days=90)
        user_id = User.objects.get(username= self.request.user)

        # Get only active banks
        banks = Banking.objects.filter(is_active=True,user_id = user_id)
        active_bank_ids = banks.values_list('id', flat=True)

        # Recent transactions from active banks only (last 3 months)
        recent_transactions = Transaction.objects.filter(
            banking__is_active=True,
            transaction_date__gte=three_months_ago,
            user_id = user_id
        ).select_related('banking')[:10]

        # Calculate totals for last 3 months from active banks only
        deposits_total = Transaction.objects.filter(
            banking__is_active=True,
            transaction_type='deposit',
            transaction_date__gte=three_months_ago,
            user_id=user_id
        ).aggregate(total=Sum('amount'))['total'] or 0

        withdrawals_total = Transaction.objects.filter(
            banking__is_active=True,
            transaction_type='withdraw',
            transaction_date__gte=three_months_ago,
            user_id=user_id
        ).aggregate(total=Sum('amount'))['total'] or 0
        charges_total = Transaction.objects.filter(
            banking__is_active=True,
            transaction_type='charges',
            transaction_date__gte=three_months_ago,
            user_id=user_id
        ).aggregate(total=Sum('amount'))['total'] or 0

        interest_total = Transaction.objects.filter(
            banking__is_active=True,
            transaction_type='interest',
            transaction_date__gte=three_months_ago,
            user_id=user_id
        ).aggregate(total=Sum('amount'))['total'] or 0
        loan_total = Transaction.objects.filter(
            banking__is_active=True,
            transaction_type='loan',
            transaction_date__gte=three_months_ago,
            user_id=user_id
        ).aggregate(total=Sum('amount'))['total'] or 0

        # Total balance across all active banks
        total_balance = sum(bank.current_balance for bank in banks)

        # Monthly activity data for chart (last 3 months) - active banks only
        monthly_data = []
        for i in range(3):
            month_start = timezone.now().replace(day=1) - timedelta(days=30 * i)
            month_end = month_start + timedelta(days=31)

            month_deposits = Transaction.objects.filter(
                banking__is_active=True,
                transaction_type='deposit',
                transaction_date__range=[month_start, month_end],
                user_id=user_id
            ).aggregate(total=Sum('amount'))['total'] or 0

            month_withdrawals = Transaction.objects.filter(
                banking__is_active=True,
                transaction_type='withdraw',
                transaction_date__range=[month_start, month_end],
                user_id=user_id
            ).aggregate(total=Sum('amount'))['total'] or 0

            month_charges = Transaction.objects.filter(
                banking__is_active=True,
                transaction_type='charges',
                transaction_date__range=[month_start, month_end],
                user_id=user_id
            ).aggregate(total=Sum('amount'))['total'] or 0

            month_loan = Transaction.objects.filter(
                banking__is_active=True,
                transaction_type='loan',
                transaction_date__range=[month_start, month_end],
                user_id=user_id
            ).aggregate(total=Sum('amount'))['total'] or 0

            month_interests = Transaction.objects.filter(
                banking__is_active=True,
                transaction_type='interest',
                transaction_date__range=[month_start, month_end],
                user_id=user_id
            ).aggregate(total=Sum('amount'))['total'] or 0

            monthly_data.append({
                'month': month_start.strftime('%B %Y'),
                'deposits': float(month_deposits),
                'withdrawals': float(month_withdrawals),
                'loans': float(month_loan),
                'interests': float(month_interests),
                'charges': float(month_charges),
                'net': float(month_deposits + month_interests  - month_withdrawals - month_loan - month_charges)
            })

        context = {
            'banks': banks,
            'recent_transactions': recent_transactions,
            'deposits_total': deposits_total + interest_total,
            'withdrawals_total': withdrawals_total + charges_total + loan_total,
            'net_change': deposits_total - withdrawals_total + interest_total - charges_total - loan_total,
            'total_balance': total_balance,
            'monthly_data': monthly_data,
        }

        return render(request, 'BankingApp/dashboard.html', context)

class BankListView(LoginRequiredMixin,View):
    def get(self,request):
        """List of all banks with their balances - showing active status"""
        # Show all banks but highlight active status
        user_id = User.objects.get(username= self.request.user)
        banks = Banking.objects.filter(user_id = user_id)
        active_banks = banks.filter(is_active=True)

        # Calculate summary statistics for active banks only
        total_balance = sum(bank.current_balance for bank in active_banks)
        total_target = sum(bank.target_amount for bank in active_banks)

        context = {
            'banks': banks,
            'active_banks': active_banks,
            'total_balance': total_balance,
            'total_target': total_target,
            'overall_progress': (total_balance / total_target * 100) if total_target > 0 else 0,
            'active_count': active_banks.count(),
            'total_count': banks.count(),
        }

        return render(request, 'BankingApp/bank_list.html', context)


class BankDetailView(LoginRequiredMixin,View):
    def get(self,request, bank_id):
        """Detail page for a specific bank with transactions and actions"""
        user_id = User.objects.get(username=self.request.user)
        bank = get_object_or_404(Banking, id=bank_id)
        transactions = bank.transactions.all()[:20]  # Last 20 transactions
        deposit_sum = bank.transactions.filter(transaction_type='deposit',user_id = user_id).aggregate(total=Sum('amount'))['total'] or 0
        withdraw_sum = bank.transactions.filter(transaction_type='withdraw',user_id = user_id).aggregate(total=Sum('amount'))['total'] or 0
        charges_sum = bank.transactions.filter(transaction_type='charges',user_id = user_id).aggregate(total=Sum('amount'))['total'] or 0
        interest_sum = bank.transactions.filter(transaction_type='interest',user_id = user_id).aggregate(total=Sum('amount'))['total'] or 0
        loan_sum = bank.transactions.filter(transaction_type='loan',user_id = user_id).aggregate(total=Sum('amount'))['total'] or 0


        form = TransactionForm()
        context = {
            'bank': bank,
            'transactions': transactions,
            'form': form,
            'deposit_sum': deposit_sum,
            'withdraw_sum': withdraw_sum,
            'charges_sum': charges_sum,
            'interest_sum': interest_sum,
            'loan_sum': loan_sum,
        }

        return render(request, 'BankingApp/bank_detail.html', context)

    def post(self,request,bank_id):
        # Only allow transactions on active banks
        user_id = User.objects.get(username=self.request.user)
        bank = get_object_or_404(Banking, id=bank_id,user_id = user_id)

        if not bank.is_active:
            messages.error(request, 'Cannot perform transactions on inactive bank accounts.')
            return redirect('BankingApp:bank_detail', bank_id=bank.id)

        form = TransactionForm(request.POST)
        if form.is_valid():
            transaction = form.save(commit=False)
            transaction.banking = bank

            # Check for sufficient funds for withdrawals
            if transaction.transaction_type == 'withdraw':
                if bank.current_balance < transaction.amount:
                    messages.error(request, 'Insufficient funds for this withdrawal.')
                    return redirect('BankingApp:bank_detail', bank_id=bank.id)

            transaction.user_id = user_id
            transaction.save()
            messages.success(request,
                             f'{transaction.get_transaction_type_display()} of ${transaction.amount} completed successfully.')
        return redirect('BankingApp:bank_detail', bank_id=bank.id)

