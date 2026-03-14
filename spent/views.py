from django.shortcuts import render,redirect,get_object_or_404,reverse
from django.views.generic.edit import CreateView,UpdateView,DeleteView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.models import User
from django.views.generic.list import ListView
from django.http import HttpResponse
from .forms import CategoryForm,SpentForm,TrackForm,TrackingForm,BudgetCategoryForm,BudgetForm,BudgetClassItemForm,BudgetItemForm,UpdateCategoryForm
from .models import Spent,Category,SavingsTracker,Tracker,Track,Tracking,NotIn,BudgetCategory,Budget,BudgetItem,BudgetClassItem,BudgetLog,WeeklySavingsTracker,SpentWeekBudget,Information
from django.views import View
import datetime
import calendar
from django.utils import timezone as tz
from django_pandas.io import read_frame
import pandas as pd
from django.db.models import Sum
from django.db import connection
from django.conf import settings
from .utils import TrackingDict
import math
from types import SimpleNamespace
from planner.utility import db_update
from .queries import weekly_saving_data_query
# Create your views here.
def index(request):
    return HttpResponse("Hello From Django")

class TawalaView(View):
    def get(self,request):
        return render(request,"spent/tawala_hotspot.html")

class WeeklyBudgetSavingsView(LoginRequiredMixin,View):
    def get(self,request):
        user = User.objects.get(username=self.request.user)
        today = datetime.datetime.now().date()
        week_start= today - datetime.timedelta(days=today.weekday())
        week_end = week_start + datetime.timedelta(days=6)
        day_prior_week = week_start - datetime.timedelta(days=1)
        with connection.cursor() as cursor:
            cursor.execute(f"""
            select distinct a.budget_id_id,strftime('%Y-%m-%d',a.week_start) as week_start,strftime('%Y-%m-%d',a.week_end) as week_end from spent_week_budget a
            where a.voided = 0 and a.user_id_id = {user.id} order by a.budget_id_id desc ,a.week_start desc
            """)
            columns = [col[0] for col in cursor.description]
            filter_list = [dict(zip(columns, row)) for row in cursor.fetchall()]
        with connection.cursor() as cursor:
            cursor.execute(f"""
            with cum as (SELECT swb.budget_id_id,swb.budget_category_id_id, sum(IFNULL(swb.amount_saved,0)) as budget_saved
            FROM spent_week_budget swb
            where swb.budget_id_id =(select budget_id_id from spent_week_budget where week_start='{week_start}' and week_end = '{week_end}' order by budget_id_id desc limit 1)
            and swb.week_end <= '{today}'
            group by swb.budget_category_id_id)

            select c.name as budget_name,d.name as budget_category,a.*,b.budget_saved from
            spent_week_budget a
            inner join spent_budget c on a.budget_id_id = c.id
            inner join spent_budgetclassitem d on a.budget_category_id_id = d.id
            left outer join cum b on a.budget_id_id = b.budget_id_id and a.budget_category_id_id = b.budget_category_id_id
            where a.week_start='{week_start}' and a.week_end = '{week_end}'
            and a.voided =0 and a.user_id_id = {user.id} and
            a.budget_id_id = (select budget_id_id from spent_week_budget where week_start='{week_start}' and week_end = '{week_end}' order by budget_id_id desc limit 1)
            """)
            columns = [col[0] for col in cursor.description]
            weekly_savings = [dict(zip(columns, row)) for row in cursor.fetchall()]
        return render(request,"spent/week_budget_savings.html",{'weekly_savings':weekly_savings,'filter_list':filter_list})
    def post(self,request):
        user = User.objects.get(username=self.request.user)
        week_filter = request.POST['week_select']
        budget_id,week_start,week_end = week_filter.split(":")
        with connection.cursor() as cursor:
            cursor.execute(f"""
                    select distinct a.budget_id_id,strftime('%Y-%m-%d',a.week_start) as week_start,
                    strftime('%Y-%m-%d',a.week_end) as week_end from spent_week_budget a
                    where a.voided = 0 and a.user_id_id = {user.id} order by a.budget_id_id desc ,a.week_start desc
                    """)
            columns = [col[0] for col in cursor.description]
            filter_list = [dict(zip(columns, row)) for row in cursor.fetchall()]
        with connection.cursor() as cursor:
            cursor.execute(f"""
                with cum as (SELECT swb.budget_id_id,swb.budget_category_id_id, sum(IFNULL(swb.amount_saved,0)) as budget_saved
                FROM spent_week_budget swb
                where swb.budget_id_id = {budget_id}
                and swb.week_end <= '{week_end}'
                group by swb.budget_category_id_id)

                select c.name as budget_name,d.name as budget_category,a.*,b.budget_saved from
                spent_week_budget a
                inner join spent_budget c on a.budget_id_id = c.id
                inner join spent_budgetclassitem d on a.budget_category_id_id = d.id
                left outer join cum b on a.budget_id_id = b.budget_id_id and a.budget_category_id_id = b.budget_category_id_id
                where a.week_start='{week_start}' and a.week_end = '{week_end}'
                and a.budget_id_id = {budget_id}
                and a.voided =0 and a.user_id_id = {user.id}
                """)
            columns = [col[0] for col in cursor.description]
            weekly_savings = [dict(zip(columns, row)) for row in cursor.fetchall()]
        return render(request,"spent/week_budget_savings.html",{'weekly_savings':weekly_savings,'filter_list':filter_list})
class BudgetCategoryView(LoginRequiredMixin,View):
    template_name = "spent/budget_category.html"
    form_class = BudgetCategoryForm
    success_url = "/budgetcategorylist"
    context_object_name = "form"
    login_url = settings.LOGIN_URL
    def get(self,request):
        form = BudgetCategoryForm()
        return render(request,self.template_name,{'form':form})
    def post(self,request):
        user = User.objects.get(username=self.request.user)
        user_id = user.id
        form = BudgetCategoryForm(request.POST)
        if(form.is_valid()):
            name = form.cleaned_data['name']
            name= name.upper().strip()
            priority= form.cleaned_data['priority']
            bcat_dub = BudgetCategory.objects.filter(name=name,user_id=user)
            if(len(bcat_dub) ==0):
                record = BudgetCategory()
                record.name=name
                record.priority=priority
                record.user_id=user
                record.save()
                return redirect('budget_category_list')
            else:
                return render(request,self.template_name,{'form':form,'error':'Budget Category Already Exists!!!'})
        else:
            return render(request, self.template_name, {'form': form, 'error': 'Some Error Ocurred!!!'})



class UpdateBudgetCategoryView(LoginRequiredMixin,UpdateView):
    template_name = "spent/update_budget_category.html"
    model = BudgetCategory
    success_url = "/budgetcategorylist"
    pk_url_kwarg = "pk"
    fields = ['name', 'priority']
    login_url = settings.LOGIN_URL
    def get(self,request,id):
        bcategory = BudgetCategory.objects.get(pk=id)
        form = BudgetCategoryForm(instance=bcategory)
        return render(request,self.template_name,{'form':form})
    def post(self,request,id):
        user = User.objects.get(username=self.request.user)
        user_id = user.id
        form = BudgetCategoryForm(request.POST)
        if (form.is_valid()):
            name = form.cleaned_data['name']
            name = name.upper().strip()
            priority = form.cleaned_data['priority']
            record = BudgetCategory.objects.get(pk=id)
            record.name = name
            record.priority = priority
            record.user_id=user
            record.save()
            return redirect('budget_category_list')
        else:
            return render(request, self.template_name, {'form': form, 'error': 'Some Error Ocurred!!!'})

class BudgetCategoryListView(LoginRequiredMixin,ListView):
    template_name ="spent/budget_category_list.html"
    model = BudgetCategory
    login_url = settings.LOGIN_URL
    def get_queryset(self):
        query_set = super().get_queryset()
        user = User.objects.get(username=self.request.user)
        query_set=query_set.filter(user_id=user,voided=0)
        return query_set

class DeleteBudgetCategoryView(LoginRequiredMixin,View):
    def get(self,request,id,*args,**kwargs):
        obj = BudgetCategory.objects.get(pk=id)
        return render(request,"spent/delete_budget_category.html",{"obj":obj})
    def post(self,request,id,*args,**kwargs):
        if request.POST['delete'] =="delete":
            category = BudgetCategory.objects.get(pk=id)
            category.voided =1
            category.save()
            return redirect("budget_category_list")
        else:
            return redirect("budget_category_list")
#................end of Budget Category Sections
# .........BUDGET SECTION ...............
class AddBudgetView(LoginRequiredMixin,View):
    template_name = "spent/create_budget.html"
    form_class = BudgetForm
    def get(self, request, *args, **kwargs):
        user = User.objects.get(username=self.request.user)
        form = BudgetForm(user)
        return render(request, self.template_name, {'form': form})

    def post(self, request, *args, **kwargs):
        user = User.objects.get(username=self.request.user)  # gets the current logged in user
        form = BudgetForm(user, request.POST)
        if form.is_valid():
            name= form.cleaned_data['name']
            description= form.cleaned_data['description']
            track_id = form.cleaned_data['track_id']
            record = Budget()
            record.name=name
            record.description = description
            record.track_id =track_id
            record.user_id =user
            record.save()
            return redirect("budget_list")
        else:
            return render(request,self.template_name,{'form':form})

class UpdateBudgetView(LoginRequiredMixin,View):
    template_name = "spent/update_budget_form.html"
    form_class = BudgetForm
    def get(self,request,id ,*args, **kwargs):
        user = User.objects.get(username=self.request.user)
        budget_data = Budget.objects.get(pk=id)
        form = BudgetForm(user,instance=budget_data)
        return render(request, self.template_name, {'form': form})
    def post(self, request, id, *args, **kwargs):
        user = User.objects.get(username=self.request.user)  # gets the current logged in user
        form = BudgetForm(user, request.POST)
        if form.is_valid():
            name= form.cleaned_data['name']
            description= form.cleaned_data['description']
            track_id = form.cleaned_data['track_id']
            record = Budget.objects.get(pk=id)
            record.name=name
            record.description = description
            record.track_id =track_id
            record.user_id =user
            record.save()
            return redirect("budget_list")
        else:
            return render(request,self.template_name,{'form':form})

class DeleteBudgetView(LoginRequiredMixin,View):
    def get(self,request,id,*args,**kwargs):
        obj = Budget.objects.get(pk=id)
        return render(request,"spent/delete_budget_form.html",{"obj":obj})
    def post(self,request,id,*args,**kwargs):
        if request.POST['delete'] =="delete":
            category = Budget.objects.get(pk=id)
            category.voided =1
            category.save()
            return redirect("budget_list")
        else:
            return redirect("budget_list")

class BudgetListView(LoginRequiredMixin,View):
    def get(self,request):
        user = User.objects.get(username=self.request.user)
        user_id = user.id
        data ={}
        with connection.cursor() as cursor:
            cursor.execute(f"""
                select b.id,
                b.name,
                b.description,
                t.start_date,
                t.end_date,
                t.amount as track_amount,
                case when total_budget.budget_total is not NULL
                then total_budget.budget_total
                else 0 end as budget_total,
                case when spent.total_spent is not NULL
                then round((spent.total_spent * 1.0) /total_budget.budget_total * 100,1)
                else 0 end as burn_rate,
                case when spent.total_spent is not NULL
                then spent.total_spent else 0 end as total_spent,
                case when total_budget.budget_total is not null and spent.total_spent is not null then
                total_budget.budget_total-spent.total_spent
                when total_budget.budget_total is null and spent.total_spent is not null   then 0-spent.total_spent
                when total_budget.budget_total is not null and spent.total_spent is null  then total_budget.budget_total-0
                else 0 end as remaining_budget,

                case when (total_budget.budget_total is not null and spent.total_spent is not null) AND
                 (total_budget.budget_total-spent.total_spent) < 0  then "surpassed budget"
                when total_budget.budget_total is null and spent.total_spent is not null  and spent.total_spent >0   then "surpassed budget"
                when total_budget.budget_total is not null and spent.total_spent is null and total_budget.budget_total !=0 then "on budget"
                else "on budget" end as budget_status
                from spent_budget b
                inner join spent_track t on t.id = b.track_id_id
                left outer join (
                select sbi.budget_id,sum(sbi.amount) as budget_total
                 from spent_budgetitem sbi
                where sbi.voided = 0 and user_id_id = {user_id}
                group by sbi.budget_id
                )total_budget on b.id = total_budget.budget_id
                left outer join (
                select bd.id,tracker.total_spent
                from spent_budget bd
                inner join (
                select tk.track_id_id,
                 sum(s.amount) as total_spent
                 from spent_tracking tk
                inner join spent_spent s on tk.spent_id_id = s.id
                where tk.voided=0 and s.voided=0 and tk.user_id_id= {user_id}
                group by tk.track_id_id
                )tracker on bd.track_id_id = tracker.track_id_id
                )spent on b.id = spent.id
                where b.voided = 0 and b.user_id_id ={user_id}
                order by t.start_date desc
            """)
            columns = [col[0] for col in cursor.description]
            data = [dict(zip(columns, row)) for row in cursor.fetchall()]
        context ={
            'datalist':data,
        }
        return render(request,'spent/budget_list.html',context)
class IndividualBudgetView(LoginRequiredMixin,View):
    def get(self,request,budget):
        user = User.objects.get(username=self.request.user) # get the user
        user_id = user.id #get the user id
        with connection.cursor() as cursor:
            cursor.execute(f"""
            select b.id,
            b.name,
            b.description,
            t.start_date,
            t.end_date,
            t.amount as track_amount,
            case when total_budget.budget_total is not NULL
            then t.amount - total_budget.budget_total
            else t.amount end as budget_diff,
            case when total_budget.budget_total is not NULL
            then total_budget.budget_total
            else 0 end as budget_total,
            case when spent.total_spent is not NULL
            then spent.total_spent else 0 end as total_spent,
            total_budget.budget_total-spent.total_spent as remaining_budget,
            case when (total_budget.budget_total-spent.total_spent) < 0 then "surpassed budget"
            else "on budget"  end as budget_status
            from spent_budget b
            inner join spent_track t on t.id = b.track_id_id
            left outer join (
            select sbi.budget_id,sum(sbi.amount) as budget_total
             from spent_budgetitem sbi
            where sbi.voided = 0 and user_id_id = {user_id}
            group by sbi.budget_id
            )total_budget on b.id = total_budget.budget_id
            left outer join (
            select bd.id,tracker.total_spent
            from spent_budget bd
            inner join (
            select tk.track_id_id,
             sum(s.amount) as total_spent
             from spent_tracking tk
            inner join spent_spent s on tk.spent_id_id = s.id
            where tk.voided=0 and s.voided=0 and tk.user_id_id= {user_id}
            group by tk.track_id_id
            )tracker on bd.track_id_id = tracker.track_id_id
            )spent on b.id = spent.id
            where b.voided = 0 and b.user_id_id ={user_id} and b.id={budget}
            order by t.start_date desc
            """)
            columns = [col[0] for col in cursor.description]
            budgetdata = [dict(zip(columns, row)) for row in cursor.fetchall()][0]

        with connection.cursor() as cursor:
            cursor.execute(f"""
            select bi.id,
            bci.name,
            bi.amount,
            case when sp.budget_spent is not NULL then sp.budget_spent
            else 0 end as budget_spent,
            case when sp.budget_spent is not NULL then (bi.amount - sp.budget_spent)
            else bi.amount end as remaining_budget,
            case when ((sp.budget_spent is not NULL) and (bi.amount - sp.budget_spent) < 0) then "surpasses budget"
            else "on budget" end as budget_status,
            bc.name as category,
            bc.priority,
            round(bi.amount/(bd.budget_total * 1.0)*100,1) as budget_perc,
			case when round(sp.budget_spent/(bi.amount * 1.0)*100) is null then 0
			else round(sp.budget_spent/(bi.amount * 1.0)*100,1)
			end as spent_perc
             from spent_budgetitem bi
            inner join spent_budgetclassitem bci on bi.budget_class_item_id = bci.id
            inner join spent_budgetcategory bc on bci.budget_category_id = bc.id
            left outer join(
            select
            spent.budget_class_category,
            spent.name,
            sum(amount) budget_spent
            from spent_budget b
            inner join (
            select trk.track_id_id,
            a.*
             from spent_tracking trk
             inner join (
            select
            ss.id as spent_id,
            ss.amount,
            ss.category_id_id,
            ct.budget_class_category,
            ct.name
             from spent_spent ss
              inner join(
            select cat.id as category_id,
            cat.category,
            bdgclass.id as budget_class_category,
            bdgclass.name
             from spent_category cat
            inner join spent_budgetclassitem bdgclass on cat.budget_category_id = bdgclass.id
            where cat.voided =0 and bdgclass.voided=0 and cat.user_id_id={user_id}) ct
            on ss.category_id_id = ct.category_id
             where ss.voided=0 and ss.user_id_id={user_id}) a
             on trk.spent_id_id = a.spent_id
             where trk.voided =0
            )spent on b.track_id_id = spent.track_id_id
            where b.voided=0 and b.id ={budget}
            group by spent.budget_class_category
            )sp on bci.id = sp.budget_class_category
            left outer join (
			select sbi.budget_id,sum(sbi.amount) as budget_total
             from spent_budgetitem sbi
            where sbi.voided = 0 and user_id_id = {user_id}
            group by sbi.budget_id
			)bd on bi.budget_id = bd.budget_id



            where bi.voided=0 and bci.voided=0 and bi.user_id_id={user_id} and bci.user_id_id ={user_id}
            and bi.budget_id={budget}
            order by bc.priority
            """)
            columns = [col[0] for col in cursor.description]
            datalist = [dict(zip(columns, row)) for row in cursor.fetchall()]

        with connection.cursor() as cursor:
            cursor.execute(f"""
             select f.*,
            round(f.spent_total/(f.budget_total*1.0)*100,1) as spent_perc,
            round(f.budget_total/(bd.budget_total*1.0)*100,1) as budget_perc
            from(
            select 		s.budget_id,
            sum(s.amount) as budget_total,
            sum(s.budget_spent) as spent_total,
            sum(s.remaining_budget) as remaining_total,
            s.category
            from
            (
            select bi.id,
			bi.budget_id,
            bci.name,
            bi.amount,
            case when sp.budget_spent is not NULL then sp.budget_spent
            else 0 end as budget_spent,
            case when sp.budget_spent is not NULL then (bi.amount - sp.budget_spent)
            else bi.amount end as remaining_budget,
            case when ((sp.budget_spent is not NULL) and (bi.amount - sp.budget_spent) < 0) then "surpasses budget"
            else "on budget" end as budget_status,
            bc.name as category,
            bc.priority
             from spent_budgetitem bi
            inner join spent_budgetclassitem bci on bi.budget_class_item_id = bci.id
            inner join spent_budgetcategory bc on bci.budget_category_id = bc.id
            left outer join(
            select
            spent.budget_class_category,
            spent.name,
            sum(amount) budget_spent
            from spent_budget b
            inner join (
            select trk.track_id_id,
            a.*
             from spent_tracking trk
             inner join (
            select
            ss.id as spent_id,
            ss.amount,
            ss.category_id_id,
            ct.budget_class_category,
            ct.name
             from spent_spent ss
              inner join(
            select cat.id as category_id,
            cat.category,
            bdgclass.id as budget_class_category,
            bdgclass.name
             from spent_category cat
            inner join spent_budgetclassitem bdgclass on cat.budget_category_id = bdgclass.id
            where cat.voided =0 and bdgclass.voided=0 and cat.user_id_id={user_id}) ct
            on ss.category_id_id = ct.category_id
             where ss.voided=0 and ss.user_id_id={user_id}) a
             on trk.spent_id_id = a.spent_id
             where trk.voided =0
            )spent on b.track_id_id = spent.track_id_id
            where b.voided=0 and b.id ={budget}
            group by spent.budget_class_category
            )sp on bci.id = sp.budget_class_category
            where bi.voided=0 and bci.voided=0 and bi.user_id_id={user_id} and bci.user_id_id ={user_id}
            and bi.budget_id={budget}
            order by bc.priority) s
            group by s.category
            order by s.priority) f

			left outer join (
			select sbi.budget_id,sum(sbi.amount) as budget_total
             from spent_budgetitem sbi
            where sbi.voided = 0 and user_id_id = {user_id}
            group by sbi.budget_id
			)bd on f.budget_id = bd.budget_id
            """)

            columns = [col[0] for col in cursor.description]
            groupdata = [dict(zip(columns, row)) for row in cursor.fetchall()]


        with connection.cursor() as cursor:
            cursor.execute(f"""
            select bi.id,
            bci.name,
            bi.amount,
            case when sp.budget_spent is not NULL then sp.budget_spent
            else 0 end as budget_spent,
            case when sp.budget_spent is not NULL then bi.amount - sp.budget_spent
            else sp.budget_spent end as budget_remaining,
            round(bi.amount/(bd.budget_total + 0.000001)*100,1) as budget_perc,
			case when round(sp.budget_spent/(bi.amount + 0.000001)*100) is null then 0
			else round(sp.budget_spent/(bi.amount + 0.000001)*100,1)
			end as spent_perc
             from spent_budgetitem bi
            inner join spent_budgetclassitem bci on bi.budget_class_item_id = bci.id
            inner join spent_budgetcategory bc on bci.budget_category_id = bc.id
            left outer join(
            select
            spent.budget_class_category,
            spent.name,
            sum(amount) budget_spent
            from spent_budget b
            inner join (
            select trk.track_id_id,
            a.*
             from spent_tracking trk
             inner join (
            select
            ss.id as spent_id,
            ss.amount,
            ss.category_id_id,
            ct.budget_class_category,
            ct.name
             from spent_spent ss
              inner join(
            select cat.id as category_id,
            cat.category,
            bdgclass.id as budget_class_category,
            bdgclass.name
             from spent_category cat
            inner join spent_budgetclassitem bdgclass on cat.budget_category_id = bdgclass.id
            where cat.voided =0 and bdgclass.voided=0 and cat.user_id_id={user_id}) ct
            on ss.category_id_id = ct.category_id
             where ss.voided=0 and ss.user_id_id={user_id}) a
             on trk.spent_id_id = a.spent_id
             where trk.voided =0
            )spent on b.track_id_id = spent.track_id_id
            where b.voided=0 and b.id ={budget}
            group by spent.budget_class_category
            )sp on bci.id = sp.budget_class_category
            left outer join (
			select sbi.budget_id,sum(sbi.amount) as budget_total
             from spent_budgetitem sbi
            where sbi.voided = 0 and user_id_id = {user_id}
            group by sbi.budget_id
			)bd on bi.budget_id = bd.budget_id
            where bi.voided=0 and bci.voided=0 and bi.user_id_id={user_id} and bci.user_id_id ={user_id}
            and bi.budget_id={budget}
            order by bc.priority
            """)
            columns = [col[0] for col in cursor.description]
            burn_data = [dict(zip(columns, row)) for row in cursor.fetchall()]
        with connection.cursor() as cursor:
            cursor.execute(f"""
            SELECT sbl.id,
            date(sbl.date_created) as log_date,
            sbl.amount,
            sbl.budget_id,
            sbl.budget_class_item_id,
            sbl.budgetitem_id,
            sbl.comment
            FROM spent_budgetlog sbl
            where sbl.budget_id = {budget}
            order by sbl.budgetitem_id,sbl.date_created desc
            """)
            columns = [col[0] for col in cursor.description]
            log_data = [dict(zip(columns, row)) for row in cursor.fetchall()]
        burn_rate = 0
        budget_completion =0
        pos_variance = 0
        neg_variance = 0


        for data in burn_data:
            if(data['amount'] == 0):
                neg_variance += data['budget_spent']
            if(data['amount'] != 0 ):
                if(data['spent_perc'] >= 100):
                    budget_completion += data['amount']
                    neg_variance  += (data['budget_spent'] - data['amount'])
                else:
                    budget_completion += data['budget_spent']
                    pos_variance += (data['amount'] - data['budget_spent'])
        burn_rate = budgetdata['total_spent']*100.0/(budgetdata['budget_total'] + 0.000001)
        budget_completion = (budget_completion / (budgetdata['budget_total']+ 0.000001)) * 100  #take care of div by zero
        burn_rate = round(burn_rate,1)
        budget_completion = round(budget_completion,1)

        #distribute the budget overspend among the other budgets e.g when someone spent in food more than the budget the excess is distribute equally to the other budgets.
        # dictionary
        for overspent_data in datalist:
            if(overspent_data['remaining_budget'] > 0 ):
                average_overspent_dist = overspent_data['remaining_budget'] / (pos_variance + 0.000001) * neg_variance
                overspent_data['weighted'] = int(overspent_data['remaining_budget'] - average_overspent_dist)
            else:
                overspent_data['weighted'] = 0

        context={
            'datalist':datalist,
            'groupdata':groupdata,
            'budgetdata':budgetdata,
            'burn_rate' : burn_rate,
            'log_data' : log_data,
            'budget_completion':budget_completion,
            'pos_variance' : pos_variance,
            'neg_variance' : neg_variance,
        }
        return render(request,'spent/individual_budget_view_form.html',context)

# ...............end of budget section
#...............start of Budget Class Item and Budget Item

class AddBudgetClassItemView(LoginRequiredMixin,View):
    template_name = "spent/add_budget_class_item_form.html"
    form_class = BudgetClassItemForm
    def get(self, request, *args, **kwargs):
        user = User.objects.get(username=self.request.user)
        form = BudgetClassItemForm(user)
        return render(request, self.template_name, {'form': form})
    def post(self, request, *args, **kwargs):
        user = User.objects.get(username=self.request.user)  # gets the current logged in user
        form = BudgetClassItemForm(user, request.POST)
        if form.is_valid():
            name= form.cleaned_data['name']
            budget_category= form.cleaned_data['budget_category']
            name = name.upper().strip()
            #check if the item already exists
            data = BudgetClassItem.objects.filter(name=name,voided=0,user_id=user)
            if(len(data)==0):
                record = BudgetClassItem()
                record.name=name
                record.budget_category = budget_category
                record.user_id =user
                record.save()
                return redirect("class_item_list")
            else:
                return render(request, self.template_name, {'form': form,'error':'Budget Class Item Already Exists!!!'})
        else:
            return render(request,self.template_name,{'form':form})


class UpdateBudgetClassItemView(LoginRequiredMixin,View):
    template_name = "spent/update_budget_class_item_form.html"
    form_class = BudgetClassItemForm
    def get(self,request,id ,*args, **kwargs):
        user = User.objects.get(username=self.request.user)
        class_data = BudgetClassItem.objects.get(pk=id)
        form = BudgetClassItemForm(user,instance=class_data)
        return render(request, self.template_name, {'form': form})
    def post(self, request, id, *args, **kwargs):
        user = User.objects.get(username=self.request.user)  # gets the current logged in user
        form = BudgetClassItemForm(user, request.POST)
        if form.is_valid():
            name = form.cleaned_data['name']
            name = name.upper().strip()
            budget_category = form.cleaned_data['budget_category']
            data = BudgetClassItem.objects.filter(name=name, voided=0, user_id=user.id)
            if (len(data) == 1):
                record = BudgetClassItem.objects.get(pk=id)
                record.name = name
                record.budget_category = budget_category
                record.user_id = user
                record.save()
                return redirect("class_item_list")
            else:
                return render(request, self.template_name, {'form': form,'error':'Error Unable to Update the Class Item'})
        else:
            return render(request,self.template_name,{'form':form})


class DeleteBudgetClassItemView(LoginRequiredMixin,View):
    def get(self,request,id,*args,**kwargs):
        obj = BudgetClassItem.objects.get(pk=id)
        return render(request,"spent/delete_budget_class_item_form.html",{"obj":obj})
    def post(self,request,id,*args,**kwargs):
        if request.POST['delete'] =="delete":
            category = BudgetClassItem.objects.get(pk=id)
            category.voided =1
            category.save()
            return redirect("class_item_list")
        else:
            return redirect("class_item_list")

class BudgetClassItemListView(LoginRequiredMixin,View):
    def get(self,request):
        user = User.objects.get(username=self.request.user)
        datalist = BudgetClassItem.objects.filter(user_id=user,voided=0)
        context={
            'datalist':datalist
        }
        return render(request,'spent/budget_class_item_list.html',context)
#.......................................................................
#.................INDIVIDUAL BUDGET ITEM ....................
class AddBudgetItemView(LoginRequiredMixin,View):
    template_name = "spent/add_budget_item_form.html"
    form_class = BudgetItemForm
    def get(self, request, *args, **kwargs):
        user = User.objects.get(username=self.request.user)
        form = BudgetItemForm(user)
        return render(request, self.template_name, {'form': form})
    def post(self, request, *args, **kwargs):
        user = User.objects.get(username=self.request.user)  # gets the current logged in user
        form = BudgetItemForm(user, request.POST)
        if form.is_valid():
            budget= form.cleaned_data['budget']
            budget_class_item= form.cleaned_data['budget_class_item']
            #check if the value already exists
            data = BudgetItem.objects.filter(budget=budget,budget_class_item=budget_class_item,voided=0,user_id=user.id)
            if(len(data)==0):
                amount = form.cleaned_data['amount']
                record = BudgetItem()
                record.budget=budget
                record.budget_class_item = budget_class_item
                record.amount = amount
                record.user_id =user
                record.save()
                return redirect("add_budget_item")
            else:
                return render(request, self.template_name, {'form': form,'error':'Budget Item Already Exists'})
        else:
            return render(request,self.template_name,{'form':form})

class UpdateBudgetItemView(LoginRequiredMixin,View):
    template_name = "spent/update_budget_item_form.html"
    form_class = BudgetItemForm
    def get(self, request,id, *args, **kwargs):
        user = User.objects.get(username=self.request.user)
        budgetItem = BudgetItem.objects.get(pk=id)
        form = BudgetItemForm(user,instance=budgetItem)
        return render(request, self.template_name, {'form': form})
    def post(self, request,id, *args, **kwargs):
        user = User.objects.get(username=self.request.user)  # gets the current logged in user
        form = BudgetItemForm(user, request.POST)
        if form.is_valid():
            budget= form.cleaned_data['budget']
            budget_class_item= form.cleaned_data['budget_class_item']
            amount = form.cleaned_data['amount']
            record = BudgetItem.objects.get(pk=id)
            backup_record = BudgetItem.objects.get(pk=id)
            record.budget=budget
            record.budget_class_item = budget_class_item
            record.amount = amount
            record.user_id =user
            record.save()
            #logging
            logging = BudgetLog()
            logging.budgetitem = backup_record
            logging.budget = backup_record.budget
            logging.budget_class_item = backup_record.budget_class_item
            logging.amount= backup_record.amount
            logging.comment = request.POST['comment']
            logging.user_id = user
            logging.save()
            return redirect("budget_item_list")
        else:
            return render(request, self.template_name, {'form': form,'error':'Some Error Ocurred!!!'})


class DeleteBudgetItemView(LoginRequiredMixin,View):
    def get(self,request,id,*args,**kwargs):
        obj = BudgetItem.objects.get(pk=id)
        return render(request,"spent/delete_budget_item_form.html",{"obj":obj})
    def post(self,request,id,*args,**kwargs):
        if request.POST['delete'] =="delete":
            category = BudgetItem.objects.get(pk=id)
            category.voided =1
            category.save()
            return redirect("budget_item_list")
        else:
            return redirect("budget_item_list")

class BudgetItemListView(LoginRequiredMixin,View):
    def get(self,request):
        user = User.objects.get(username=self.request.user)
        user_id =user.id
        today = datetime.datetime.now().date()
        start_date = datetime.date(today.year, today.month, 1)
        end_date = datetime.date(today.year, today.month, calendar.monthrange(today.year, today.month)[1])
        datalist={}
        with connection.cursor() as cursor:
            cursor.execute(f"""
            select sbi.id, b.name as budget,
            bci.name as budget_class_item,
             sbi.amount
             from spent_budgetitem sbi
            inner join spent_budget b on sbi.budget_id = b.id
            inner join spent_budgetclassitem bci on sbi.budget_class_item_id = bci.id
            inner join spent_track tr on b.track_id_id = tr.id
            where tr.start_date < CURRENT_DATE AND tr.end_date > CURRENT_DATE AND sbi.voided = 0
            and b.voided=0 and bci.voided=0
            and tr.voided=0 and sbi.user_id_id ={user_id}

            """)
            columns = [col[0] for col in cursor.description]
            datalist = [dict(zip(columns, row)) for row in cursor.fetchall()]
            budgets = Budget.objects.filter(user_id=user,voided=0)
        context={
            'datalist':datalist,
            'budgets':budgets
        }
        return render(request,'spent/budget_item_list.html',context)
    def post(self,request):
        user = User.objects.get(username=self.request.user)
        user_id = user.id
        budget = request.POST['budget']
        datalist = {}
        with connection.cursor() as cursor:
            cursor.execute(f"""
                    select sbi.id,b.name as budget,
                    bci.name as budget_class_item,
                     sbi.amount
                     from spent_budgetitem sbi
                    inner join spent_budget b on sbi.budget_id = b.id
                    inner join spent_budgetclassitem bci on sbi.budget_class_item_id = bci.id
                    inner join spent_track tr on b.track_id_id = tr.id
                    where b.id={budget} AND sbi.voided = 0
                    and b.voided=0 and bci.voided=0
                    and tr.voided=0 and sbi.user_id_id ={user_id}

                    """)
            columns = [col[0] for col in cursor.description]
            datalist = [dict(zip(columns, row)) for row in cursor.fetchall()]
        budgets = Budget.objects.filter(user_id=user, voided=0)
        context = {
            'datalist': datalist,
            'budgets': budgets
        }
        return render(request, 'spent/budget_item_list.html', context)
#...............................................................................
class CategoryView(LoginRequiredMixin,View):
    template_name = "spent/category_page.html"
    form_class= CategoryForm
    success_url = "/addCategory"
    context_object_name="form"
    login_url = settings.LOGIN_URL

    def get(self,request):
        user = User.objects.get(username=self.request.user)
        form = CategoryForm(user)
        return render(request,self.template_name,{'form':form})
    def post(self,request):
        user = User.objects.get(username=self.request.user)
        user_id =user.id
        form = CategoryForm(user,request.POST)
        if(form.is_valid()):
            date = form.cleaned_data['date']
            category = form.cleaned_data['category']
            category = category.upper().strip()
            as_savings = form.cleaned_data['as_savings']
            budget_category  = form.cleaned_data['budget_category']
            cat_dub = Category.objects.filter(category=category,user_id=user)
            if(len(cat_dub)==0):
                record = Category()
                record.date=date
                record.category=category
                record.as_savings = as_savings
                record.budget_category=budget_category
                record.user_id=user
                record.save()
                return redirect('category_list')
            else:
                return render(request,self.template_name,{'form':form,'error':'Error Category Already Exists!!!'})
        else:
            return render(request,self.template_name,{'form':form})


class CategoryListView(LoginRequiredMixin,ListView):
    template_name ="spent/category_list.html"
    model = Category
    login_url = settings.LOGIN_URL
    def get_queryset(self):
        query_set = super().get_queryset()
        user = User.objects.get(username=self.request.user)
        query_set=query_set.filter(user_id=user,voided=0)
        return query_set

class UpdateCategoryView(LoginRequiredMixin,View):
    template_name = "spent/category_page.html"
    model= Category
    success_url="/"
    pk_url_kwarg = "pk"
    fields=['date','category','as_savings','inactive','budget_category']
    login_url = settings.LOGIN_URL
    def get(self,request,id):
        user = User.objects.get(username=self.request.user)
        user_id =user.id
        category = Category.objects.get(pk=id)
        form = UpdateCategoryForm(user,instance=category)
        return render(request, self.template_name, {'form': form})
    def post(self,request,id):
        user = User.objects.get(username=self.request.user)
        user_id =user.id
        form = UpdateCategoryForm(user, request.POST)
        if (form.is_valid()):
            date = form.cleaned_data['date']
            category = form.cleaned_data['category']
            category =category.upper().strip()
            as_savings = form.cleaned_data['as_savings']
            inactive = form.cleaned_data['inactive']
            budget_category = form.cleaned_data['budget_category']
            #retrieve the record to update
            record = Category.objects.get(pk=id)
            record.date = date
            record.category = category
            record.as_savings = as_savings
            record.inactive =inactive
            record.budget_category = budget_category
            record.user_id =user
            record.save()
            return redirect('category_list')
        else:
            return render(request, self.template_name, {'form': form})
class DeleteCategoryView(LoginRequiredMixin,View):
    def get(self,request,id,*args,**kwargs):
        obj = Category.objects.get(pk=id)
        return render(request,"spent/delete_category.html",{"obj":obj})
    def post(self,request,id,*args,**kwargs):
        if request.POST['delete'] =="delete":
            category = Category.objects.get(pk=id)
            category.voided =1
            category.save()
            return redirect("category_list")
        else:
            return redirect("category_list")


class AddSpentView(LoginRequiredMixin,View):
    template_name="spent/spent_page.html"
    login_url = settings.LOGIN_URL
    def get(self,request,*args,**kwargs):
        user = User.objects.get(username=self.request.user)
        form = SpentForm(user)
        return render(request,self.template_name,{'form':form})
    def post(self,request,*args,**kwargs):
        user = User.objects.get(username=self.request.user) #gets the current logged in user
        today = datetime.datetime.now().date() # useful for weekly savings
        week_start = today - datetime.timedelta(days=today.weekday())  # useful for weekly savings
        week_end = week_start + datetime.timedelta(days=6)  # useful for weekly savings

        form = SpentForm(user,request.POST)
        if form.is_valid():
            date= form.cleaned_data['date']
            category_id = form.cleaned_data['category_id'].id
            amount = form.cleaned_data['amount']
            comment = form.cleaned_data['comment']
            user_id = User.objects.get(username=self.request.user)

            already = Spent.objects.filter(date=date,category_id=category_id,user_id=user_id,voided=0) #checking if spent already exists
            if(len(already) == 0):
                result = Spent()
                result.date=date
                result.category_id = Category.objects.get(id=category_id)
                result.amount=amount
                result.comment = comment
                result.user_id = user_id
                result.save()
                #create tracking for tracking between a certain period
                track = Track.objects.filter(start_date__lte=date,end_date__gte=date,user_id=user_id,voided=0).order_by('-start_date')
                if(len(track) !=0): # if there is a track define in that period
                    recent_track = track[0] #get the recent track
                    #get the Tracker with the recent track id and category_id and use it to create tracking in the spent Model
                    tracker = Tracker.objects.filter(track_id=recent_track,category_id=Category.objects.get(id=category_id),voided=0,user_id=user_id)
                    if(len(tracker)==1):
                        new_tracking = Tracking()
                        new_tracking.user_id=user_id
                        new_tracking.spent_id = Spent.objects.get(pk=result.id)
                        new_tracking.track_id=recent_track
                        new_tracking.save() # create a new tracking
                #update the savingsTracker if category has as_savings to true
                if result.category_id.as_savings:
                    savings = SavingsTracker()
                    savings.spent_id = Spent.objects.get(pk=result.id) #update the spent record id
                    savings.user_id=user_id
                    savings.save()
                # Create or Update Weekly update.
                with connection.cursor() as cursor:
                    cursor.execute(weekly_saving_data_query(today,week_start,week_end,user))
                    columns = [col[0] for col in cursor.description]
                    weekly_savings = [dict(zip(columns, row)) for row in cursor.fetchall()]
                    #call update method
                create_update_weekly_savings(weekly_savings,user) #update/create weekly savings
            else:
                return HttpResponse("You have already spent that item, do you wish to update the item???")
            return redirect("daily_list")
        else:
            return render(request, self.template_name, {'form': form})
class UpdateSpentView(LoginRequiredMixin,View):
    template_name="spent/update_spent_form.html"
    model= Spent
    form_class = SpentForm
    #fields =["date","category_id","amount"]
    pk_url_kwarg ="pk"
    success_url="/dailylist"
    login_url = settings.LOGIN_URL
    def get(self,request,id):
        user = User.objects.get(username=self.request.user)
        spent = Spent.objects.get(pk=id)
        form = SpentForm(user, instance=spent)
        return render(request,self.template_name,{'form':form})
    def post(self,request,id):
        user = User.objects.get(username=self.request.user)
        today = datetime.datetime.now().date() # useful for weekly savings
        week_start = today - datetime.timedelta(days=today.weekday())  # useful for weekly savings
        week_end = week_start + datetime.timedelta(days=6)  # useful for weekly savings
        spent = Spent.objects.get(pk=id)
        form = SpentForm(user,request.POST)
        if(form.is_valid()):
            date = form.cleaned_data['date']
            category_id = form.cleaned_data['category_id']
            amount = form.cleaned_data['amount']
            comment = form.cleaned_data['comment']
            record = Spent.objects.get(pk=id)
            record.date=date
            record.category_id =category_id
            record.amount=amount
            record.comment = comment
            record.user_id=user
            record.save()

        # Create or Update Weekly update.
            with connection.cursor() as cursor:
                cursor.execute(weekly_saving_data_query(today,week_start,week_end,user))
                columns = [col[0] for col in cursor.description]
                weekly_savings = [dict(zip(columns, row)) for row in cursor.fetchall()]
                #call update method
            create_update_weekly_savings(weekly_savings,user) #update/create weekly savings
            return redirect('daily_list')
        else:
            return render(request, self.template_name, {'form': form,'error':'Some Error Ocurred'})
class DeleteSpentView(LoginRequiredMixin,View):
    template_name="spent/delete_spent_form.html"
    model =Spent
    pk_url_kwarg="pk"
    success_url='/dailylist'
    login_url = settings.LOGIN_URL
    def get(self,request,id,*args,**kwargs):
        object=get_object_or_404(Spent,pk=id)
        return render(request,self.template_name,{"obj":object})
    def post(self,request,id,*args,**kwargs):
        if request.POST['delete'] == "delete":
            Spent.objects.filter(pk=id).update(voided=1)
            return redirect('daily_list')
        else:
            return redirect('daily_list')

class DailyListView(LoginRequiredMixin,View):
    login_url = settings.LOGIN_URL
    def get(self,request,*args,**kwargs):
        user = User.objects.get(username=self.request.user)
        db_update(user.id)
        today =tz.now().date()
        week_start = today - datetime.timedelta(days=today.weekday())
        week_end = week_start + datetime.timedelta(days=6)
        spents = Spent.objects.filter(date=today,voided=0,user_id=user)
        weekspents = Spent.objects.filter(date__gte=week_start,date__lte=week_end,voided=0,user_id=user)
        current_track = Track.objects.filter(start_date__lte=today,end_date__gte=today,user_id = user)
        if len(current_track) > 0 :
            current_track = current_track[0]
        else:
            current_track =SimpleNamespace(end_date=datetime.date(2000,1,1), id =0,daily_limit=0,amount=0)
        user_id = user.id
        totals = spents.aggregate(totals=Sum('amount')) #calculate aggregated Spent
        weektotals = weekspents.aggregate(totals=Sum('amount')) #calculate weekly spent for the week

        #
        if current_track.end_date > today:
            days_remaining = (current_track.end_date - today).days
        else:
            days_remaining = 1000000

        with connection.cursor() as cursor:
            cursor.execute(f"""
                select si.item_date,
                si.item_name,
                ci.category_name,
                si.status,
                si.estimated_price
                from shopper_shoppingitem si
                inner join shopper_categoryitem ci on si.category_id_id = ci.id
                where si.voided = 0
                and si.urgent = 'yes'
                and si.status <> 'completed'
                and si.user_id_id ={user.id}
                """)
            columns = [col[0] for col in cursor.description]
            urgent_data = [dict(zip(columns,row)) for row in cursor.fetchall()]

        with connection.cursor() as cursor:
            cursor.execute(f"""
                select sum(s.amount) as amount_spent
                from spent_tracking tr
                inner join spent_spent s on tr.spent_id_id = s.id
                where tr.voided = 0 and s.voided = 0 
                and (tr.track_id_id, tr.user_id_id) in
                (
                select t.id,t.user_id_id
                from spent_track t where t.id = {current_track.id}
                and t.voided =0
                )
            """)
            columns = [col[0] for col in cursor.description]
            amount_spent = [dict(zip(columns,row)) for row in cursor.fetchall()]
            if amount_spent[0]['amount_spent'] is not None:
                amount_spent_total = amount_spent[0]['amount_spent']
            else:
                amount_spent_total = 0




        with connection.cursor() as cursor:
                cursor.execute(f"""
                    SELECT sum(c.amount) as total_debt
                     FROM credits_credit c
                     where c.voided=0 and c.paid=0 and c.user_id_id={user_id}
                """)
                columns = [col[0] for col in cursor.description]
                debt_owed = [dict(zip(columns,row)) for row in cursor.fetchall()]
        with connection.cursor() as cursor:
            cursor.execute(f"""
                SELECT sum(s.amount) debt_paid
                 FROM credits_credit c
                 inner join (
                 SELECT
                cs.amount,
                cs.debt_id_id
                 FROM credits_creditservice cs
                 where cs.voided=0
                 )s on c.id = s.debt_id_id
                 where c.voided=0 and c.paid=0 and c.user_id_id={user_id}
            """)
            columns = [col[0] for col in cursor.description]
            debt_paid = [dict(zip(columns,row)) for row in cursor.fetchall()]

            if len(debt_owed)>0:
                debt_owed= debt_owed[0]['total_debt']
            else:
                debt_owed = 0
            if len(debt_paid)>0:
                debt_paid= debt_paid[0]['debt_paid']
            else:
                debt_paid = 0
            if(debt_paid is None):
                debt_paid = 0
            if(debt_owed is None):
                debt_owed =0
        if weektotals.get('totals',0) is None:
            wktotals = 0
        else:
            wktotals = weektotals.get('totals',0)
        school_info_list = Information.objects.filter(voided=0,start_date__lte=today, end_date__gte=today,user_id = user)
        if len(school_info_list) > 0:
            school_info = school_info_list[0]
        else:
            school_info = None
        return render(request,"spent/daily_spent.html",{
            'daily_spent':spents,'totals':totals.get('totals',0),'weektotals':wktotals,
            'daily_limit':current_track.daily_limit,'weekly_limit' : current_track.daily_limit * 7,
            'debt':(debt_owed-debt_paid),
            'weekly_deficit':(current_track.daily_limit *7)-wktotals,
            'urgent_data': urgent_data,'num':len(urgent_data),
            'amount_spent':amount_spent_total,
            'track_amount':current_track.amount,
            'daily_estimate':math.floor(((current_track.amount-amount_spent_total)/days_remaining)),
            'school_info':school_info,
        })


class AllListView(LoginRequiredMixin,View):
    login_url = settings.LOGIN_URL
    def get(self,request,*args,**kwargs):
        user = User.objects.get(username=self.request.user)
        now = tz.now()
        new_data=[]
        # start_month =datetime.date(now.year,now.month,1)
        # end_month = datetime.date(now.year,now.month,calendar.monthrange(now.year,now.month)[1])
        month_data = Spent.objects.filter(voided=0,user_id=user)
        #calculate the total budget spending done so far and what is remaining
        spent_amount = 0
        budget_amount =0
        remaining_amount = 0
        tracks=Track.objects.filter(start_date__lte=now.date(),end_date__gte=now.date(),voided=0,user_id=user)
        if(len(tracks) ==1):
            spent_amount=Tracking.objects.filter(track_id=tracks[0]).aggregate(Sum('spent_id__amount'))
            spent_amount=spent_amount['spent_id__amount__sum']
            if(spent_amount == None):
                spent_amount =0
            budget_amount = tracks[0].amount
            remaining_amount =budget_amount - spent_amount
        #........................................................................
        if(len(month_data) > 0): # account for empty list
            month_df = read_frame(month_data,fieldnames=['date','category_id','amount'])
            month_df.index = pd.to_datetime(month_df['date']) #use date as datetime_index inorder to perform resample
            month_cumm = month_df.resample('D').sum()
            month_cumm = month_cumm.reset_index()#reset back index to 0 index based.
            month_cumm = month_cumm.sort_values('date',ascending=False)
            data = month_cumm.to_dict() #convert dataframe to dictionary

            new_data = []
            for (x, y) in zip(list(data['date'].values()), list(data['amount'].values())): #combine both date and amount in a tuple
                if(y == 0): # remove days where there were no spent
                    continue
                new_data.append((x,y))
            totals = None
            if new_data != []:
                df =pd.DataFrame(new_data)
                totals = df[1].sum()
            return render(request,"spent/all_list.html",{'data':new_data,'totals':totals,
                                                              'budget_amount':budget_amount,
                                                              'remaining_amount':remaining_amount,
                                                              'spent_amount':spent_amount})
        else:
            return render(request,"spent/all_list.html")


class SpentInASpecificDayView(LoginRequiredMixin,View):
    login_url = settings.LOGIN_URL
    def get(self,request,day,*args,**kwargs):
        user = User.objects.get(username=self.request.user)
        today = datetime.datetime.fromisoformat(day)
        today = today.date()
        spents = Spent.objects.filter(date=today,voided=0,user_id=user)
        totals = spents.aggregate(totals=Sum('amount'))
        return render(request, "spent/daily_spent.html", {'daily_spent': spents,'totals':totals['totals']})
class MonthlyListView(LoginRequiredMixin,View):
    login_url = settings.LOGIN_URL
    def get(self,request,*args,**kwargs):
        user = User.objects.get(username=self.request.user)
        now = tz.now()
        new_data=[]
        start_month =datetime.date(now.year,now.month,1)
        end_month = datetime.date(now.year,now.month,calendar.monthrange(now.year,now.month)[1])
        days_spent = (now.date()-start_month).days + 1
        month_data = Spent.objects.filter(date__gte=start_month,date__lte=end_month,voided=0,user_id=user)
        #calculate the total budget spending done so far and what is remaining
        spent_amount = 0
        budget_amount =0
        remaining_amount = 0
        tracks=Track.objects.filter(start_date__lte=now.date(),end_date__gte=now.date(),voided=0,user_id=user)
        if(len(tracks) ==1):
            spent_amount=Tracking.objects.filter(track_id=tracks[0],spent_id__voided=0).aggregate(Sum('spent_id__amount'))
            spent_amount=spent_amount['spent_id__amount__sum']
            if(spent_amount == None):
                spent_amount =0
            budget_amount = tracks[0].amount
            remaining_amount = budget_amount - spent_amount
        #........................................................................
        if(len(month_data) > 0): # account for empty list
            month_df = read_frame(month_data,fieldnames=['date','category_id','amount'])
            month_df.index = pd.to_datetime(month_df['date']) #use date as datetime_index inorder to perform resample
            month_cumm = month_df.resample('D').sum()
            month_cumm = month_cumm.reset_index()#reset back index to 0 index based.
            month_cumm = month_cumm.sort_values('date',ascending=False)
            data = month_cumm.to_dict() #convert dataframe to dictionary

            new_data = []
            for (x, y) in zip(list(data['date'].values()), list(data['amount'].values())): #combine both date and amount in a tuple
                if(y == 0): # remove days where there were no spent
                    continue
                new_data.append((x,y))
            totals = None
            if new_data != []:
                df =pd.DataFrame(new_data)
                totals = df[1].sum()
            return render(request,"spent/daily_summary.html",{'data':new_data,'totals':totals,
                                                              'budget_amount':budget_amount,
                                                              'remaining_amount':remaining_amount,
                                                              'spent_amount':spent_amount,'average':math.ceil(totals/days_spent)})
        else:
            return render(request,"spent/daily_summary.html")

class DeleteBunchView(View,LoginRequiredMixin):
    login_url = settings.LOGIN_URL
    def get(self, request, day, *args, **kwargs):
        user = User.objects.get(username=self.request.user)
        date = datetime.datetime.fromisoformat(day)
        date = date.date()
        spents = Spent.objects.filter(date=date,voided=0,user_id=user)
        return render(request,"spent/delete_bunch.html",{'data':spents})
    def post(self,request,*args,**kwargs):
        user = User.objects.get(username=self.request.user)
        ids = request.POST.getlist('delete_ids')
        for id in ids:
            Spent.objects.filter(pk=id).update(voided=1)
        return redirect("monthly_list")


#savings view
class SavingsList(LoginRequiredMixin,ListView):
    template_name = "spent/savings_list.html"
    model = SavingsTracker
    login_url = settings.LOGIN_URL
    def get_queryset(self):
        query_set = super().get_queryset()# get the list
        user = User.objects.get(username=self.request.user) #filter for the current logged in user
        query_set = query_set.filter(user_id=user,voided=0)
        return query_set

class CreateTrackView(LoginRequiredMixin,CreateView):
    login_url = settings.LOGIN_URL
    model = Track
    template_name = "spent/create_track.html"
    form_class =TrackForm
    success_url = "/"

    def form_valid(self, form):
        user = User.objects.get(username=self.request.user)
        form.instance.user_id= user
        return super().form_valid(form)

class UpdateTrackView(LoginRequiredMixin,UpdateView):
    model = Track
    template_name = "spent/create_track.html"
    form_class = TrackForm
    login_url = settings.LOGIN_URL
    success_url = "/"
    pk_url_kwarg = "pk"
class TrackListView(LoginRequiredMixin,ListView):
    model = Track
    template_name = "spent/track_list.html"
    login_url = settings.LOGIN_URL

    def get_queryset(self):
        queryset= super().get_queryset()
        user = User.objects.get(username=self.request.user)
        queryset = queryset.filter(user_id=user,voided=0)
        return queryset




class CreateTrackingView(LoginRequiredMixin,View):
    login_url = settings.LOGIN_URL
    def get(self,request,*args,**kwargs):
        user = User.objects.get(username=self.request.user)
        choices = Track.objects.filter(user_id=user).values_list('id', 'start_date')
        return render(request,"spent/create_tracking.html",{"select_values":choices})

    def post(self,request,*args,**kwargs):
        track_id = None
        val = request.POST['tracks_submit'] # the value of button pressed
        user = User.objects.get(username=self.request.user)
        trackDict = TrackingDict()
        track_id = request.POST['tracks']
        choices = Track.objects.filter(user_id=user).values_list('id', 'start_date')
        if val == "Generate trackings Category":
            all_category = Category.objects.filter(user_id=user,voided=0,inactive=0).values('id','category')
            track = Track.objects.get(pk=track_id)
            tracker = Tracker.objects.filter(track_id=track,voided=0)
            for x in all_category:
                trackDict.addCategory(x['category'],x['id'])
            for cat in tracker:
                if cat.category_id.category in trackDict.get_tracking_list():
                    trackDict.updateCategory(cat.category_id.category)
            return render(request,"spent/create_tracking.html",{"select_values":choices,"categories":trackDict.get_tracking_list()})


        if val == "Update the Tracking list":
            track_id = request.POST['tracks']
            track = Track.objects.get(pk=track_id) #get the Track instance to add to Tracker
            ids = request.POST.getlist('cat_list')
            for id in ids: #use all checked boxes in the create_tracking template
                c=Category.objects.get(pk=id) # all the
                if(len(Tracker.objects.filter(track_id=track,category_id=c))==0): #check for dublicate
                    tracker = Tracker()
                    tracker.category_id = c
                    tracker.user_id=user
                    tracker.track_id = track
                    tracker.save()
                #elif(len(Tracker.objects.filter(track_id=track,category_id=c,voided=1))> 0): #this may blow up
                #    tracker = Tracker.objects.get(track_id=track,category_id=c,voided=1)
                #    tracker.voided=0 # we dont need this
                #    tracker.save()

            trackers = Tracker.objects.filter(track_id=track_id)
            trackers.update(voided=1)
            ### void all the Trackers and then unvoid all the selected inorder to use the in
            Tracker.objects.filter(track_id=track_id,category_id__in=ids).update(voided=0)

            # Laststep
            all_category = Category.objects.filter(user_id=user, voided=0,inactive=False)
            for x in all_category:
                trackDict.addCategory(x.category, x.id)
            for cat in trackers:
                trackDict.updateCategory(cat.category_id.category)
            return render(request, "spent/create_tracking.html",
                          {"select_values": choices, "categories": trackDict.get_tracking_list()})
        return render(request, "spent/create_tracking.html", {"select_values": choices})

class TrackingListView(LoginRequiredMixin,ListView):
    model = Tracking
    login_url = settings.LOGIN_URL
    template_name = "spent/tracking_list.html"
    def get_queryset(self):
        user = User.objects.get(username=self.request.user)
        queryset = super().get_queryset()
        queryset=queryset.filter(user_id=user,voided=0)
        return queryset

class TrackerListView(LoginRequiredMixin,View):
    model =Tracker
    login_url = settings.LOGIN_URL
    template_name = "spent/tracker_list.html"
    def get(self,request,pk,*args,**kwargs):
        track =Track.objects.get(pk=pk)
        trackers = Tracker.objects.filter(track_id=track,voided=0)
        return render(request,self.template_name,{'trackers':trackers,'track':track})
class TrackerSummary(LoginRequiredMixin,View):
    model =Tracking
    login_url = settings.LOGIN_URL
    template_name = "spent/tracking_summary.html"
    def get(self,request,pk,*args,**kwargs):
        track = Track.objects.get(pk=pk)
        trackinglist = model.objects.get(track_id=track,voided=0)
        summary = tracklinglist.aggregate(total=Sum('spent_id'))
        return render(request,self.template_name)



class TrackerSpentListView(LoginRequiredMixin,View):
    model =Tracking
    login_url = settings.LOGIN_URL
    template_name = "spent/tracker_list.html"
    def get(self,request,pk,*args,**kwargs):
        track =Track.objects.get(pk=pk)
        #get info about Track selected start_date,end_date,budget_amount,spent_amount,remaining_amount
        start_date = track.start_date
        end_date = track.end_date
        days_spent = 1
        new_data=[]
        budget_amount =track.amount
        user = User.objects.get(username=self.request.user)
        trackings = Tracking.objects.filter(track_id=track,voided=0,user_id=user,spent_id__voided=0) # check if the spent was voided.
        spent_amount=trackings.aggregate(Sum('spent_id__amount'))
        spent_amount=spent_amount['spent_id__amount__sum']
        if(spent_amount == None):
            spent_amount =0
        remaining_amount = budget_amount - spent_amount

        if(len(trackings) > 0): # account for empty list
            track_data = Tracking.objects.filter(track_id=track,voided=0,user_id=user,spent_id__voided=0).values('spent_id__date','spent_id__amount')
            track_dict ={}
            #convert the list-dict to dict-list for easier export to pandas Dataframe
            for keys in track_data[0].keys():
                track_dict[keys]=[]
            for data in track_data:
                for key,val in data.items():
                    track_dict[key].append(val)
            days_spent=(max(track_dict['spent_id__date'])-min(track_dict['spent_id__date'])).days + 1



            #month_df = read_frame(track_data,fieldnames=['date','category_id','amount'])
            month_df=pd.DataFrame(track_dict)
            month_df.index = pd.to_datetime(month_df['spent_id__date']) #use date as datetime_index inorder to perform resample
            month_cumm = month_df.resample('D').sum()
            month_cumm = month_cumm.reset_index()#reset back index to 0 index based.
            month_cumm = month_cumm.sort_values('spent_id__date',ascending=False)
            data = month_cumm.to_dict() #convert dataframe to dictionary

            new_data = []
            for (x, y) in zip(list(data['spent_id__date'].values()), list(data['spent_id__amount'].values())): #combine both date and amount in a tuple
                if(y == 0): # remove days where there were no spent
                    continue
                new_data.append((x,y))
            totals = None
            if new_data != []:
                df =pd.DataFrame(new_data)
                totals = df[1].sum()
            return render(request,"spent/tracking_spent_list.html",{'data':new_data,'totals':totals,'start_date':start_date,'end_date':end_date,
                                                              'budget_amount':budget_amount,
                                                              'remaining_amount':remaining_amount,
                                                             'average':math.ceil(totals/days_spent),'budget_average':math.ceil(budget_amount/((end_date-start_date).days + 1))})
        return render(request,'spent/tracking_spent_list.html')




class SummaryGraphView(LoginRequiredMixin,View):
    def get(self,request,track,*args,**kwargs):
        track_data = Track.objects.get(pk=track)
        user = User.objects.get(username=self.request.user)
        sql =f"""select
        category.category,
        final.amount_spent
        from (
        select distinct sum(cat.amount) as amount_spent,
        cat.category_id_id
        from (
        select s.date,
        s.amount,
        s.category_id_id
         from spent_spent s
        inner join (
        select tng.spent_id_id
         from spent_tracking tng
        where tng.track_id_id = {track}
        and voided=0 and tng.user_id_id = {user.id}) t
        on s.id = t.spent_id_id
        where s.voided=0 ) cat
        group by cat.category_id_id) final
        left outer join (
        	select
        	c.id,
        	c.category
        	 from spent_category c
        )category on final.category_id_id = category.id
        order by final.amount_spent desc
         """
        with connection.cursor() as cursor:
            cursor.execute(sql)
            columns = [col[0] for col in cursor.description]
            graph_data = [dict(zip(columns,row)) for row in cursor.fetchall()]
            top_ten_data = graph_data[0:10]
            bottom_ten_data =graph_data[-10:]
        context ={
                'graph':graph_data,
                'top':top_ten_data,
                'bottom':bottom_ten_data,
                'track':track_data,
            }
        return render(request,'credits/summary_graph.html',context)


class PeriodSummaryGraphView(LoginRequiredMixin,View):
    def get(self,request):
        user = User.objects.get(username=self.request.user)
        today = datetime.datetime.now().date()
        start_date = datetime.date(today.year, today.month, 1)
        end_date = today
        month_days = calendar.monthrange(today.year, today.month)[1]
        days_between = (end_date - start_date).days + 1

        sql =f"""
        select
        category.category,
        final.amount_spent,
        final.amount_spent/{days_between} as daily_average,
        final.amount_spent/{days_between} *{month_days} as month_estimate
        from (
        select distinct sum(cat.amount) as amount_spent,
        cat.category_id_id
        from (
        select s.date,
        s.amount,
        s.category_id_id
         from spent_spent s
		 where s.date between "{start_date}" and "{end_date}"
		 and s.voided=0 and s.user_id_id = {user.id}
         ) cat
        group by cat.category_id_id) final
        left outer join (
        	select
        	c.id,
        	c.category
        	 from spent_category c
        )category on final.category_id_id = category.id
        order by final.amount_spent desc
         """
        with connection.cursor() as cursor:
            cursor.execute(sql)
            columns = [col[0] for col in cursor.description]
            graph_data = [dict(zip(columns,row)) for row in cursor.fetchall()]
        context ={
                'graph':graph_data,
                'start_date':start_date,
                'end_date':end_date,
                'days': days_between,
                'month_days':month_days,
                'today':today,
            }
        return render(request,'spent/period_summary_graph.html',context)

    def post(self, request):
        user = User.objects.get(username=self.request.user)
        today = datetime.datetime.now().date()
        start_date = request.POST['start_date']
        end_date = request.POST['end_date']
        start_date = datetime.datetime.strptime(start_date,"%Y-%m-%d").date()
        end_date = datetime.datetime.strptime(end_date,"%Y-%m-%d").date()
        days_between = (end_date - start_date).days + 1
        month_days = calendar.monthrange(today.year, today.month)[1]
        sql = f"""
        select
        category.category,
        final.amount_spent,
        final.amount_spent/{days_between} as daily_average,
        final.amount_spent/{days_between} *{month_days} as month_estimate
        from (
        select distinct sum(cat.amount) as amount_spent,
        cat.category_id_id
        from (
        select s.date,
        s.amount,
        s.category_id_id
         from spent_spent s
         where s.date between "{start_date}" and "{end_date}"
         and s.voided=0 and s.user_id_id = {user.id}
         ) cat
        group by cat.category_id_id) final
        left outer join (
            select
            c.id,
            c.category
             from spent_category c
        )category on final.category_id_id = category.id
        order by final.amount_spent desc
         """
        with connection.cursor() as cursor:
            cursor.execute(sql)
            columns = [col[0] for col in cursor.description]
            graph_data = [dict(zip(columns, row)) for row in cursor.fetchall()]
        context = {
            'graph': graph_data,
            'start_date': start_date,
            'end_date': end_date,
            'days':days_between,
            'month_days':month_days,
            'today':today,

        }
        return render(request, 'spent/period_summary_graph.html', context)

class PeriodIndividualView(LoginRequiredMixin,View):
    def get(self,request,start_date,end_date,category):
        user = User.objects.get(username=self.request.user)
        sql =f"""
            select s.id,s.date,c.category,s.amount,s.comment from
            spent_spent s
            inner join spent_category c
            on s.category_id_id = c.id
            where s.voided=0 and c.voided=0
            and s.user_id_id ={user.id}
            and c.category = '{category}'
            and s.date between '{start_date}' and '{end_date}'
            order by s.date desc
            """
        with connection.cursor() as cursor:
            cursor.execute(sql)
            columns = [col[0] for col in cursor.description]
            table_data = [dict(zip(columns,row)) for row in cursor.fetchall()]
        with connection.cursor() as cursor:
            cursor.execute(f"""
            select sum(s.amount) as total_amount from
            spent_spent s
            inner join spent_category c
            on s.category_id_id = c.id
            where s.voided=0 and c.voided=0
            and s.user_id_id = {user.id}
            and c.category = "{category}"
            and s.date between "{start_date}" and "{end_date}"
            """)
            columns = [col[0] for col in cursor.description]
            sum_total = [dict(zip(columns,row)) for row in cursor.fetchall()][0]['total_amount']
        context ={
                'table_data':table_data,
                'start_date':start_date,
                'end_date':end_date,
                'total': sum_total,
                'category': category,
            }
        return render(request,'spent/single_element_graph_selection.html',context)


class BudgetEstimationView(LoginRequiredMixin,View):
    def get(self,request):
        user = User.objects.get(username=self.request.user)
        today = datetime.datetime.now().date()
        today_str = today.strftime("%Y-%m-%d")
        start_date = datetime.date(today.year, today.month, 1)
        end_date = today
        month_days = calendar.monthrange(today.year, today.month)[1]
        days_between = (end_date - start_date).days + 1
        days_remaining = month_days - days_between
        sql =f"""
        select
        (select c.name from spent_budgetclassitem c where c.id = current_budget.budget_category_id) as category,
        current_budget.budget_amount as ba,
        current_budget.budget_spent as bs,
        current_budget.budget_deficit as bd,

    	case when spent_specified.spent_stddev is NULL then 0
            else spent_specified.spent_stddev  end as specified_period_stddev,

        case when spent_specified.amount_spent is NULL then 0
        else spent_specified.amount_spent  end as specified_period_spent,
        case when  spent_specified.month_estimate is NULL then 0
        else spent_specified.month_estimate end as current_month_estimate,
        case when spent_specified.month_estimate is NULL then 0
        else current_budget.budget_amount - spent_specified.month_estimate end  as budget_minus_estimate,
        case when spent_specified.daily_estimate is NULL then 0 else spent_specified.daily_estimate  end as daily_estimate,
        case when spent_specified.daily_estimate is NULL then 0 else (spent_specified.daily_estimate * {days_remaining})  end as estimate_remaining,
        case when spent_specified.daily_estimate is NULL then 0
        else
        current_budget.budget_deficit - (spent_specified.daily_estimate * {days_remaining}) end as remaining_month_est
        from(
        select a.budget_category_id,
        b.budget_amount,
        a.budget_spent,
        b.budget_amount-a.budget_spent as budget_deficit
        from(
        select distinct bs.budget_category_id,sum(bs.amount) as budget_spent
        from(
        select spent.amount,category.budget_category_id
        from spent_spent spent
        inner join spent_category category on
        spent.category_id_id  = category.id
        where spent.voided= 0 and spent.user_id_id ={user.id}
        and spent.id in (
        SELECT tracking.spent_id_id
        FROM spent_tracking tracking
        where tracking.voided =0
        and tracking.user_id_id = {user.id}
        and tracking.track_id_id = (SELECT distinct track.id
        FROM spent_track track
        where track.voided = 0
        and track.user_id_id = {user.id} and track.start_date < "{today_str}"
        order by track.end_date desc
        limit 1)
        ))bs
        group by bs.budget_category_id) a
        inner join (
        select distinct ba.budget_class_item_id, sum(ba.amount) as budget_amount
        from(
        select bi.id,bi.amount,bi.budget_class_item_id from spent_budgetitem bi
        where bi.voided=0
        and bi.budget_id =
        (
        select b.id from spent_budget b
        where b.track_id_id =
        (SELECT track.id
        FROM spent_track track
        where track.voided = 0
        and track.user_id_id = {user.id} and track.start_date < "{today_str}"
        order by track.end_date desc
        limit 1
        )

        )
        )ba
        group by ba.budget_class_item_id

        )b on a.budget_category_id = b.budget_class_item_id

        ) current_budget
        left outer  join (
        select
                final.budget_category_id,
                final.amount_spent,
                final.spent_stddev,
                final.amount_spent/{days_between} as daily_estimate,
                final.amount_spent/{days_between} *{month_days} as month_estimate
                from (
            	SELECT DISTINCT
                SUM(cat.amount) AS amount_spent,
                cat.budget_category_id,
                ROUND(
                    SQRT(
                        SUM((cat.amount - (SELECT AVG(inner_cat.amount)
                                           FROM (
                                                SELECT s.amount
                                                FROM spent_spent s
                                                INNER JOIN spent_category c
                                                ON s.category_id_id = c.id
                                                WHERE s.date BETWEEN "{start_date}" and "{end_date}"
                                                  AND s.voided = 0
                                                  AND s.user_id_id = {user.id}
                                                  AND c.budget_category_id = cat.budget_category_id
                                           ) AS inner_cat)) *
                            (cat.amount - (SELECT AVG(inner_cat.amount)
                                           FROM (
                                                SELECT s.amount
                                                FROM spent_spent s
                                                INNER JOIN spent_category c
                                                ON s.category_id_id = c.id
                                                WHERE s.date BETWEEN "{start_date}" and "{end_date}"
                                                  AND s.voided = 0
                                                  AND s.user_id_id = {user.id}
                                                  AND c.budget_category_id = cat.budget_category_id
                                           ) AS inner_cat))
                        ) /
                        (COUNT(cat.amount) - 1)
                    ), 2
                ) AS spent_stddev
            FROM (
                SELECT
                    s.date,
                    s.amount,
                    c.budget_category_id
                FROM spent_spent s
                INNER JOIN spent_category c ON s.category_id_id = c.id
                WHERE s.date BETWEEN "{start_date}" and "{end_date}"
                  AND s.voided = 0
                  AND s.user_id_id = {user.id}
            ) cat
            GROUP BY cat.budget_category_id

            		) final
                            order by final.amount_spent desc


        )spent_specified on  current_budget.budget_category_id = spent_specified.budget_category_id
        order by current_budget.budget_amount desc
         """
        with connection.cursor() as cursor:
            cursor.execute(sql)
            columns = [col[0] for col in cursor.description]
            graph_data = [dict(zip(columns,row)) for row in cursor.fetchall()]
        context ={
                'graph':graph_data,
                'start_date':start_date,
                'end_date':end_date,
                'days': days_between,
                'month_days':month_days,
                'today':today,
                'days_remaining': days_remaining,
            }

        return render(request,'spent/budget_estimate.html',context)

    def post(self, request):
        user = User.objects.get(username=self.request.user)
        today = datetime.datetime.now().date()
        start_date = request.POST['start_date']
        end_date = request.POST['end_date']
        start_date = datetime.datetime.strptime(start_date,"%Y-%m-%d").date()
        end_date = datetime.datetime.strptime(end_date,"%Y-%m-%d").date()
        days_between = (end_date - start_date).days + 1
        month_days = calendar.monthrange(today.year, today.month)[1]
        today_str = today.strftime("%Y-%m-%d")
        days_remaining = month_days - (today.day)
        sql = f"""
        select
        (select c.name from spent_budgetclassitem c where c.id = current_budget.budget_category_id) as category,
        current_budget.budget_amount as ba,
        current_budget.budget_spent as bs,
        current_budget.budget_deficit as bd,


    	case when spent_specified.spent_stddev is NULL then 0
            else spent_specified.spent_stddev  end as specified_period_stddev,

        case when spent_specified.amount_spent is NULL then 0
        else spent_specified.amount_spent  end as specified_period_spent,
        case when  spent_specified.month_estimate is NULL then 0
        else spent_specified.month_estimate end as current_month_estimate,
        case when spent_specified.month_estimate is NULL then 0
        else current_budget.budget_amount - spent_specified.month_estimate end  as budget_minus_estimate,
        case when spent_specified.daily_estimate is NULL then 0 else spent_specified.daily_estimate  end as daily_estimate,
        case when spent_specified.daily_estimate is NULL then 0 else (spent_specified.daily_estimate * {days_remaining})  end as estimate_remaining,
        case when spent_specified.daily_estimate is NULL then 0
        else
        current_budget.budget_deficit - (spent_specified.daily_estimate * {days_remaining}) end as remaining_month_est
        from(
        select a.budget_category_id,
        b.budget_amount,
        a.budget_spent,
        b.budget_amount-a.budget_spent as budget_deficit
        from(
        select distinct bs.budget_category_id,sum(bs.amount) as budget_spent
        from(
        select spent.amount,category.budget_category_id
        from spent_spent spent
        inner join spent_category category on
        spent.category_id_id  = category.id
        where spent.voided= 0 and spent.user_id_id ={user.id}
        and spent.id in (
        SELECT tracking.spent_id_id
        FROM spent_tracking tracking
        where tracking.voided =0
        and tracking.user_id_id = {user.id}
        and tracking.track_id_id = (SELECT distinct track.id
        FROM spent_track track
        where track.voided = 0
        and track.user_id_id = {user.id} and track.start_date < "{today_str}"
        order by track.end_date desc
        limit 1)
        ))bs
        group by bs.budget_category_id) a
        inner join (
        select distinct ba.budget_class_item_id, sum(ba.amount) as budget_amount
        from(
        select bi.id,bi.amount,bi.budget_class_item_id from spent_budgetitem bi
        where bi.voided=0
        and bi.budget_id =
        (
        select b.id from spent_budget b
        where b.track_id_id =
        (SELECT track.id
        FROM spent_track track
        where track.voided = 0
        and track.user_id_id = {user.id} and track.start_date < "{today_str}"
        order by track.end_date desc
        limit 1
        )

        )
        )ba
        group by ba.budget_class_item_id

        )b on a.budget_category_id = b.budget_class_item_id

        ) current_budget
        left outer  join (
        select
                final.budget_category_id,
                final.amount_spent,
                final.spent_stddev,
                final.amount_spent/{days_between} as daily_estimate,
                final.amount_spent/{days_between} *{month_days} as month_estimate
                from (
            	SELECT DISTINCT
                SUM(cat.amount) AS amount_spent,
                cat.budget_category_id,
                ROUND(
                    SQRT(
                        SUM((cat.amount - (SELECT AVG(inner_cat.amount)
                                           FROM (
                                                SELECT s.amount
                                                FROM spent_spent s
                                                INNER JOIN spent_category c
                                                ON s.category_id_id = c.id
                                                WHERE s.date BETWEEN "{start_date}" and "{end_date}"
                                                  AND s.voided = 0
                                                  AND s.user_id_id = {user.id}
                                                  AND c.budget_category_id = cat.budget_category_id
                                           ) AS inner_cat)) *
                            (cat.amount - (SELECT AVG(inner_cat.amount)
                                           FROM (
                                                SELECT s.amount
                                                FROM spent_spent s
                                                INNER JOIN spent_category c
                                                ON s.category_id_id = c.id
                                                WHERE s.date BETWEEN "{start_date}" and "{end_date}"
                                                  AND s.voided = 0
                                                  AND s.user_id_id = {user.id}
                                                  AND c.budget_category_id = cat.budget_category_id
                                           ) AS inner_cat))
                        ) /
                        (COUNT(cat.amount) - 1)
                    ), 2
                ) AS spent_stddev
            FROM (
                SELECT
                    s.date,
                    s.amount,
                    c.budget_category_id
                FROM spent_spent s
                INNER JOIN spent_category c ON s.category_id_id = c.id
                WHERE s.date BETWEEN "{start_date}" and "{end_date}"
                  AND s.voided = 0
                  AND s.user_id_id = {user.id}
            ) cat
            GROUP BY cat.budget_category_id

            		) final
                            order by final.amount_spent desc


        )spent_specified on  current_budget.budget_category_id = spent_specified.budget_category_id
        order by current_budget.budget_amount desc




         """
        with connection.cursor() as cursor:
            cursor.execute(sql)
            columns = [col[0] for col in cursor.description]
            graph_data = [dict(zip(columns, row)) for row in cursor.fetchall()]
        context = {
            'graph': graph_data,
            'start_date': start_date,
            'end_date': end_date,
            'days':days_between,
            'month_days':month_days,
            'today':today,
            'days_remaining': days_remaining,

        }
        return render(request, 'spent/budget_estimate.html', context)

class CategoryIndividualView(LoginRequiredMixin,View):
    def get(self,request,start_date,end_date,category):
        user = User.objects.get(username=self.request.user)
        sql =f"""
            select s.id,s.date,c.category,s.amount,s.comment from
            spent_spent s
            inner join spent_category c
            on s.category_id_id = c.id
            inner join spent_budgetclassitem bci on c.budget_category_id = bci.id
            where s.voided=0 and c.voided=0
            and s.user_id_id ={user.id}
            and bci.name = '{category}'
            and s.date between '{start_date}' and '{end_date}'
            order by s.date desc
            """
        with connection.cursor() as cursor:
            cursor.execute(sql)
            columns = [col[0] for col in cursor.description]
            table_data = [dict(zip(columns,row)) for row in cursor.fetchall()]
        with connection.cursor() as cursor:
            cursor.execute(f"""
            select sum(s.amount) as total_amount from
            spent_spent s
            inner join spent_category c
            on s.category_id_id = c.id
            inner join spent_budgetclassitem bci on c.budget_category_id = bci.id
            where s.voided=0 and c.voided=0
            and s.user_id_id = {user.id}
            and bci.name = "{category}"
            and s.date between "{start_date}" and "{end_date}"
            """)
            columns = [col[0] for col in cursor.description]
            sum_total = [dict(zip(columns,row)) for row in cursor.fetchall()][0]['total_amount']
        context ={
                'table_data':table_data,
                'start_date':start_date,
                'end_date':end_date,
                'total': sum_total,
                'category':category,
            }
        return render(request,'spent/single_element_graph_selection.html',context)
# Create your views here.


class AmortizedBudgetEstimatesView(LoginRequiredMixin,View):
    def get(self,request):
        user = User.objects.get(username=self.request.user)
        user_id = user.id
        with connection.cursor() as cursor:
            cursor.execute(f"""
                select
                b.name as name,
                a.average as average,
                a.estimate_1_month as estimate_1_month,
                a.estimate_3_months as estimate_3_months,
                a.estimate_6_months as estimate_6_months
                from(
                select  month.budget_category_id,
                (month.estimate_1_month + quarter.estimate_3_months + half.estimate_6_months)/3 as average,
                month.estimate_1_month,
                quarter.estimate_3_months,
                half.estimate_6_months
                from(
                select
                    final.budget_category_id,
                    final.amount_spent,
                    final.amount_spent/30 * 30 as estimate_1_month
                    from (
                    select distinct sum(cat.amount) as amount_spent,
                    cat.budget_category_id
                    from (
                    select s.date,
                    s.amount,
                    c.budget_category_id
                     from spent_spent s
                     inner join spent_category c on s.category_id_id = c.id
                	 where s.date between date('now','-30 days') and date('now')
                	 and s.voided=0 and s.user_id_id = {user.id}
                     ) cat
                    group by cat.budget_category_id) final
                    order by final.amount_spent desc) month
                    left outer join(
                        select
                        final.budget_category_id,
                        final.amount_spent,
                        final.amount_spent/90 * 30 as estimate_3_months
                        from (
                        select distinct sum(cat.amount) as amount_spent,
                        cat.budget_category_id
                        from (
                        select s.date,
                        s.amount,
                        c.budget_category_id
                         from spent_spent s
                         inner join spent_category c on s.category_id_id = c.id
                		 where s.date between date('now','-90 days') and date('now')
                		 and s.voided=0 and s.user_id_id = {user.id}
                         ) cat
                        group by cat.budget_category_id) final
                        order by final.amount_spent desc

                    )quarter on month.budget_category_id = quarter.budget_category_id
                    left outer join (
                        select
                        final.budget_category_id,
                        final.amount_spent,
                        final.amount_spent/180 * 30 as estimate_6_months
                        from (
                        select distinct sum(cat.amount) as amount_spent,
                        cat.budget_category_id
                        from (
                        select s.date,
                        s.amount,
                        c.budget_category_id
                         from spent_spent s
                         inner join spent_category c on s.category_id_id = c.id
                		 where s.date between date('now','-180 days') and date('now')
                		 and s.voided=0 and s.user_id_id = {user.id}
                         ) cat
                        group by cat.budget_category_id) final
                        order by final.amount_spent desc
                    )half on month.budget_category_id = half.budget_category_id) a
                    inner join (
                        SELECT sbc.id,
                        sbc.name
                        FROM spent_budgetclassitem sbc
                        where sbc.voided =0 and user_id_id = {user.id}
                        )b on a.budget_category_id = b.id
            """)
            columns = [col[0] for col in cursor.description]
            estimates = [dict(zip(columns,row)) for row in cursor.fetchall()]
        context = {
            'estimates':estimates,
            }
        return render(request,'spent/amortized_budget_estimates.html',context)


class BudgetPerformanceView(LoginRequiredMixin,View):
    def get(self,request):
        user = User.objects.get(username=self.request.user)
        user_id = user.id
        with connection.cursor() as cursor:
            cursor.execute(f"""
                select b.id,b.name from spent_budget b
                inner join spent_track t on b.track_id_id = t.id
                where b.user_id_id = {user.id} and t.voided =0
                order by t.start_date desc
                limit 24
            """)
            columns = [col[0] for col in cursor.description]
            budget_list = [dict(zip(columns,row)) for row in cursor.fetchall()]

        with connection.cursor() as cursor:
            budget_performance ={}
            for b in budget_list:
                budget = b['id']
                budget_performance[budget] = {'name' : b['name']}
                cursor.execute(f"""
                select distinct final.budget_id,
                sum(final.amount) as budget_amount,
                sum(final.budget_spent) as budget_spent,
                sum(final.budget_completed) as budget_completed,
                round((sum(final.budget_spent)/(sum(final.amount)+ 0.000001) * 100),1) as budget_spent_perc,
                round((sum(final.budget_completed)/(sum(final.amount)+ 0.000001) * 100),1) as budget_completed_perc

                from
                (
                select bi.budget_id,
                            bi.amount,
                            case when sp.budget_spent is not NULL then sp.budget_spent
                            else 0 end as budget_spent,
                			case when bi.amount = 0 then 0
                			when sp.budget_spent is null then 0
                			when round(sp.budget_spent/(bi.amount + 0.000001),1) > 1 then bi.amount
                			else sp.budget_spent end as budget_completed
                             from spent_budgetitem bi
                            inner join spent_budgetclassitem bci on bi.budget_class_item_id = bci.id
                            inner join spent_budgetcategory bc on bci.budget_category_id = bc.id
                            left outer join(
                            select
                            spent.budget_class_category,
                            spent.name,
                            sum(amount) budget_spent
                            from spent_budget b
                            inner join (
                            select trk.track_id_id,
                            a.*
                             from spent_tracking trk
                             inner join (
                            select
                            ss.id as spent_id,
                            ss.amount,
                            ss.category_id_id,
                            ct.budget_class_category,
                            ct.name
                             from spent_spent ss
                              inner join(
                            select cat.id as category_id,
                            cat.category,
                            bdgclass.id as budget_class_category,
                            bdgclass.name
                             from spent_category cat
                            inner join spent_budgetclassitem bdgclass on cat.budget_category_id = bdgclass.id
                            where cat.voided =0 and bdgclass.voided=0 and cat.user_id_id={user_id}) ct
                            on ss.category_id_id = ct.category_id
                             where ss.voided=0 and ss.user_id_id={user_id}) a
                             on trk.spent_id_id = a.spent_id
                             where trk.voided =0
                            )spent on b.track_id_id = spent.track_id_id
                            where b.voided=0 and b.id ={budget}
                            group by spent.budget_class_category
                            )sp on bci.id = sp.budget_class_category
                            left outer join (
                			select sbi.budget_id,sum(sbi.amount) as budget_total
                             from spent_budgetitem sbi
                            where sbi.voided = 0 and user_id_id = {user_id}
                            group by sbi.budget_id
                			)bd on bi.budget_id = bd.budget_id
                            where bi.voided=0 and bci.voided=0 and bi.user_id_id={user_id} and bci.user_id_id ={user_id}
                            and bi.budget_id={budget}
                            order by bc.priority
                            )final
                """)
                columns = [col[0] for col in cursor.description]
                perf_dict = [dict(zip(columns,row)) for row in cursor.fetchall()][0]
                budget_performance[budget]['performance'] = perf_dict
        context ={
            'performance_data' : budget_performance,
            }
        return render(request,'spent/budget_performance.html',context)



class WeeklyAnalysisView(LoginRequiredMixin,View):
    login_url = settings.LOGIN_URL
    def get(self,request,*args,**kwargs):
        user = User.objects.get(username=self.request.user)
        today =tz.now().date()
        quarter = (today.month - 1) // 3 + 1
        quarter_start_date = datetime.date(today.year, (quarter - 1) * 3 + 1, 1)
        if quarter == 4:
            quarter_end_date = datetime.date(today.year + 1, 1, 1) - datetime.timedelta(days=1)
        else:
            quarter_end_date = datetime.date(today.year, quarter * 3 + 1, 1) - datetime.timedelta(days=1)

        #with connection.cursor() as cursor:
            #cursor.execute(f"""
        data =pd.read_sql(f"""
        SELECT sp.id,
        sp.date,
        sp.amount
        FROM spent_spent sp
        where sp.voided=0 and sp.user_id_id = {user.id}
        and sp.date between '{quarter_start_date}' and '{quarter_end_date}'
        """,connection)
        #columns = [col[0] for col in cursor.description]
        #data = [dict(zip(columns, row)) for row in cursor.fetchall()]

        #df = pd.DataFrame.from_dict(data)
        df = data.set_index(data['date'])
        df = df[['amount']]
        df.index = pd.to_datetime(df.index)
        #df['date'] = pd.to_datetime(df.index)
        df_weekly = df.resample('W').sum()

        df_weekly['weekend'] = df_weekly.index
        df_weekly =df_weekly.sort_values(by=['weekend'],ascending=False)
        df_weekly['weekstart'] = df_weekly['weekend'].apply(lambda x: x - datetime.timedelta(6))
        weekly_list = tuple(zip(list(df_weekly['weekstart']),list(df_weekly['weekend']),list(df_weekly['amount'])))

        return render(request,"spent/weekly_analysis.html",{'weekly_list':weekly_list,'quarter_start':quarter_start_date,'quarter_end':quarter_end_date})

class CreateSavingsTrackingView(LoginRequiredMixin,View):
    login_url = settings.LOGIN_URL
    def get(self,request,*args,**kwargs):
        user = User.objects.get(username=self.request.user)
        choices = Track.objects.filter(user_id=user).values_list('id', 'start_date')
        return render(request,"spent/create_savings_tracking.html",{"select_values":choices})

    def post(self,request,*args,**kwargs):
        track_id = None
        val = request.POST['tracks_submit'] # the value of button pressed
        user = User.objects.get(username=self.request.user)
        trackDict = TrackingDict()
        track_id = request.POST['tracks']
        choices = Track.objects.filter(user_id=user).values_list('id', 'start_date')
        if val == "Generate trackings Category":
            all_category = BudgetClassItem.objects.filter(user_id=user,voided=0).values('id','name')
            track = Track.objects.get(pk=track_id)
            tracker = WeeklySavingsTracker.objects.filter(track_id=track,voided=0)
            for x in all_category:
                trackDict.addCategory(x['name'],x['id'])
            for cat in tracker:
                if cat.category_id.name in trackDict.get_tracking_list():
                    trackDict.updateCategory(cat.category_id.name)
            return render(request,"spent/create_savings_tracking.html",{"select_values":choices,"categories":trackDict.get_tracking_list()})


        if val == "Update the Tracking list":
            track_id = request.POST['tracks']
            track = Track.objects.get(pk=track_id) #get the Track instance to add to Tracker
            ids = request.POST.getlist('cat_list')
            for id in ids: #use all checked boxes in the create_tracking template
                c=BudgetClassItem.objects.get(pk=id) # all the
                if(len(WeeklySavingsTracker.objects.filter(track_id=track,category_id=c))==0): #check for dublicate
                    tracker = WeeklySavingsTracker()
                    tracker.category_id = c
                    tracker.user_id=user
                    tracker.track_id = track
                    tracker.save()
                #elif(len(Tracker.objects.filter(track_id=track,category_id=c,voided=1))> 0): #this may blow up
                #    tracker = Tracker.objects.get(track_id=track,category_id=c,voided=1)
                #    tracker.voided=0 # we dont need this
                #    tracker.save()

            trackers = WeeklySavingsTracker.objects.filter(track_id=track_id)
            trackers.update(voided=1)
            ### void all the Trackers and then unvoid all the selected inorder to use the in
            WeeklySavingsTracker.objects.filter(track_id=track_id,category_id__in=ids).update(voided=0)

            # Laststep
            all_category = BudgetClassItem.objects.filter(user_id=user, voided=0)
            for x in all_category:
                trackDict.addCategory(x.name, x.id)
            for cat in trackers:
                trackDict.updateCategory(cat.category_id.name)
            return render(request, "spent/create_savings_tracking.html",
                          {"select_values": choices, "categories": trackDict.get_tracking_list()})
        return render(request, "spent/create_savings_tracking.html", {"select_values": choices})


class UpdateWeeklySurplusView(LoginRequiredMixin,View):
    def post(self,request):
        today = datetime.datetime.now().date()
        one_week_ago = today - datetime.timedelta(weeks=1)
        last_day_of_week = one_week_ago + datetime.timedelta(days=(6 - one_week_ago.weekday()))
        SpentWeekBudget.objects.filter(week_end__lte=last_day_of_week, locked=False).update(locked=True)  # lock everything that is more than one week from the current date

        id = int(request.POST['week_cat'])
        amount_bf = int(request.POST['amountBf'])
        amount_saved = int(request.POST['amountSaved'])
        if(amount_saved > 0):
            spent_obj = SpentWeekBudget.objects.get(pk=id)
            if(spent_obj.locked is False):
                spent_obj.amount_bf = amount_bf
                spent_obj.amount_saved = amount_saved + spent_obj.amount_saved
                spent_obj.save()
        return redirect("weekly_savings")



#utils functions
def create_update_weekly_savings(data,user):
    for item in data:
        budget_id = item['budget_id']
        budget_category_id = item['budget_category_id']
        week_start = item['week_start']
        week_end = item['week_end']
        budget_amount= item['budget_amount']
        budget_spent_start = item['spent_at_start_this_week']
        week_budget = item['week_budget']
        week_spent = item['spent_this_week']
        week_remaining = item['week_remaining']

        with connection.cursor() as cursor:
            cursor.execute(f"""
            select *
            from spent_week_budget a
            where a.budget_id_id={budget_id} and a.budget_category_id_id = {budget_category_id}
            and a.week_start='{week_start}' and a.week_end='{week_end}'
            """)
            columns = [col[0] for col in cursor.description]
            savings_list = [dict(zip(columns, row)) for row in cursor.fetchall()]
        if len(savings_list) > 0 :
            spent_obj = SpentWeekBudget.objects.get(pk=savings_list[0]['id'])
            spent_obj.budget_amount=budget_amount
            spent_obj.budget_spent_start=budget_spent_start
            spent_obj.week_budget=week_budget
            spent_obj.week_spent=week_spent
            spent_obj.week_remaining=week_remaining
            spent_obj.save()
        else:
            new_spent_obj = SpentWeekBudget()
            new_spent_obj.budget_id = Budget.objects.get(pk=budget_id)
            new_spent_obj.budget_category_id = BudgetClassItem.objects.get(pk=budget_category_id)
            new_spent_obj.week_start = week_start
            new_spent_obj.week_end = week_end
            new_spent_obj.budget_amount = budget_amount
            new_spent_obj.budget_spent_start = budget_spent_start
            new_spent_obj.week_budget = week_budget
            new_spent_obj.week_spent = week_spent
            new_spent_obj.week_remaining = week_remaining
            new_spent_obj.user_id = user
            new_spent_obj.save()