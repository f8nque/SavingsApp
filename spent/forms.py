from .models import Spent,Category,Tracker,Tracking,Track,Budget,BudgetCategory,BudgetClassItem,BudgetItem
from django import forms
from django.utils import timezone as tz

class CategoryForm(forms.ModelForm):
    def __init__(self,user,*args,**kwargs):
        super(CategoryForm, self).__init__(*args, **kwargs)
        self.fields['budget_category'].queryset = BudgetClassItem.objects.filter(user_id=user, voided=0)
    class Meta:
        model =Category
        fields =['date','category','as_savings','budget_category']
        widgets = {
            'date': forms.TextInput(attrs={'type': 'date','value':tz.now().date(),'class':'form-group form-control'}),
            'category':forms.TextInput(attrs={'class':'form-group form-control'}),
            'as_savings':forms.CheckboxInput(attrs={'class':'form-group'}),
            'budget_category':forms.Select(attrs={'class':'form-group form-control'})
        }

class UpdateCategoryForm(forms.ModelForm):
    def __init__(self,user,*args,**kwargs):
        super(UpdateCategoryForm, self).__init__(*args, **kwargs)
        self.fields['budget_category'].queryset = BudgetClassItem.objects.filter(user_id=user, voided=0)
    class Meta:
        model =Category
        fields =['date','category','as_savings','inactive','budget_category']
        widgets = {
            'date': forms.TextInput(attrs={'type': 'date','value':tz.now().date(),'class':'form-group form-control'}),
            'category':forms.TextInput(attrs={'class':'form-group form-control'}),
            'inactive':forms.CheckboxInput(attrs={'class':'form-group'}),
            'as_savings':forms.CheckboxInput(attrs={'class':'form-group'}),
            'budget_category':forms.Select(attrs={'class':'form-group form-control'})
        }


class SpentForm(forms.ModelForm):
    def __init__(self,user,*args,**kwargs):
        super(SpentForm,self).__init__(*args,**kwargs)
        self.fields['category_id'].queryset=Category.objects.filter(user_id=user,voided=0,inactive=0)
    class Meta:
        model = Spent
        exclude= ['user_id','date_created','voided']
        widgets ={
            'date': forms.TextInput(attrs={'type':'date','class':'date_field','value':tz.now().date(),'class':'form-group form-control'}),
            'category_id':forms.Select(attrs={'class':'form-group form-control'}),
            'amount':forms.NumberInput(attrs={'class':'form-group form-control'}),
            'comment': forms.TextInput(attrs={'class':'form-group form-control'}),
        }

class TrackForm(forms.ModelForm):
    class Meta:
        model = Track
        exclude=['voided','user_id','date_created','date_updated']
        widgets={
            'start_date':forms.DateInput(attrs={'type':'date','class':'form-control form-group'}),
            'end_date': forms.DateInput(attrs={'type': 'date','class':'form-control form-group'}),
            'amount': forms.NumberInput(attrs={'class':'form-control form-group'}),
            'daily_limit': forms.NumberInput(attrs={'class':'form-control form-group'}),
        }

class TrackingForm(forms.Form):
    #choices = Track.objects.filter().values_list('id','start_date')
    tracks = forms.ChoiceField()

class BudgetCategoryForm(forms.ModelForm):
    class Meta:
        model = BudgetCategory
        exclude=['voided','user_id','date_created','date_updated']
        widgets={
            'name': forms.TextInput(attrs={'class': 'form-group form-control'})

        }


class BudgetForm(forms.ModelForm):
    def __init__(self,user,*args,**kwargs):
        super(BudgetForm,self).__init__(*args,**kwargs)
        self.fields['track_id'].queryset=Track.objects.filter(user_id=user,voided=0)
    class Meta:
        model = Budget
        exclude= ['user_id','date_created','voided','date_updated']
        widgets ={
            'track_id': forms.Select(attrs={'class':'form-group form-control'}),
            'name':forms.TextInput(attrs={'class':'form-group form-control'}),
            'description': forms.TextInput(attrs={'class': 'form-group form-control'}),
        }

class BudgetClassItemForm(forms.ModelForm):
    def __init__(self,user,*args,**kwargs):
        super(BudgetClassItemForm,self).__init__(*args,**kwargs)
        self.fields['budget_category'].queryset=BudgetCategory.objects.filter(user_id=user,voided=0)
    class Meta:
        model = BudgetClassItem
        exclude= ['user_id','date_created','voided','date_updated']
        widgets ={
            'name':forms.TextInput(attrs={'class':'form-group form-control'}),
            'budget_category': forms.Select(attrs={'class':'form-group form-control'})
        }

class BudgetItemForm(forms.ModelForm):
    def __init__(self,user,*args,**kwargs):
        super(BudgetItemForm,self).__init__(*args,**kwargs)
        self.fields['budget'].queryset=Budget.objects.filter(user_id=user,voided=0)
        self.fields['budget_class_item'].queryset = BudgetClassItem.objects.filter(user_id=user, voided=0)
    class Meta:
        model = BudgetItem
        exclude= ['user_id','date_created','voided','date_updated']
        widgets ={
            'budget': forms.Select(attrs={'class': 'form-group form-control'}),
            'budget_class_item': forms.Select(attrs={'class':'form-group form-control'}),
            'amount': forms.NumberInput(attrs={'class': 'form-group form-control'}),

        }