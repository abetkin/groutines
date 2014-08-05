# -*- coding: utf-8 -*-

from django.contrib.auth.models import User

from groutines import (make_groutine, FunctionCall, Event, switch, greenlet,
                       wait_any, listen_any,)
from dec import groutine
import IPython, ipdb

class GMiddleware(object):
    
    @property
    def functions(self):
        return [
            start_view, check_permissions,
            fill_user,
        ]
    
    def __init__(self):
        self.groutines = set()
    
    def process_view(self, request, view_func, view_args, view_kwargs):
        for func in self.functions:
            gr = make_groutine(func)
            self.groutines.add(gr)
        
    
    def process_response(self, request, response):
        for gr in tuple(self.groutines):
            gr.throw() # killing it
            self.groutines.remove(gr)
        return response

@groutine()
def start_view():
    view, request = FunctionCall(
            'rest_framework.views.APIView.dispatch').wait('ENTER')
    Event('DISPATCH').fire(view, request)

@groutine(FunctionCall('rest_framework.views.APIView.check_permissions'),
          typ='ENTER')
def check_permissions(view, request, **kw):
    return True


@groutine('DISPATCH')
def fill_user(view, request):
    _, snippet = FunctionCall((view, 'pre_save')).wait(typ='ENTER')
    snippet.owner = User.objects.get(username='vitalii')


@groutine('DISPATCH')
def deserialization(view, request):
    srlzer, data, files = FunctionCall('rest_framework.serializers.Serializer'
                                       '.from_native',
                                       argnames=['data', 'files']
                                       ).wait('ENTER')
    
    print srlzer, data
    
    
    code_field = srlzer.fields['code']
    print FunctionCall((code_field, 'field_from_native')).wait()
 
    def _fcalls():
        for field_name, field in srlzer.fields.items():
            yield FunctionCall(
                (field, 'field_from_native'),
                argnames=['data', 'files', 'field_name', 'into'])
    while True:
        field_name, into = wait_any(list(_fcalls()))[-2:]
        print field_name, '->', into.get(field_name, '----')


#@groutine(FunctionCall('rest_framework.serializers.Field'
#                        '.field_from_native') ,once=False)
#def _1(field, data, files, field_name, into, **kw):
#    print field_name, '->', into.get(field_name, '----')

@groutine(FunctionCall('rest_framework.mixins.Response',
                       argnames=('data', 'status'),
                       restore_asap=True),
          once=False)
def make_responses_raise_exc(data, status, *args, **kw):
    if status // 100 != 2:
        raise Exception(data)

#@groutine('DESER_FIELD', once=False)
#def deserialize_field(field_name, data, into):
#    event = FunctionCall('rest_framework.serializers.Serializer.field_from_native')
#    event.wait('ENTER')
#    event.wait('EXIT')
    
#@groutine(1)
#def f1(view, request):
#    print request.path

