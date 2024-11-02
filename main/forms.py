# queueapp/forms.py
from django import forms

class JoinQueueForm(forms.Form):
    number_of_people = forms.IntegerField(min_value=1, required=True)

    

