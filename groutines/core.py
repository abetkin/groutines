# -*- coding: utf-8 -*-

from .util import object_from_name, is_classmethod

import greenlet
import collections
import wrapt
import inspect

class ExplicitNone(object): pass

class ForceReturn(object):
    def __init__(self, value):
        self.value = value

class Listener(object):
    '''
    Listens to an event.
    '''
    
    def __init__(self, event, condition=None, groutine=None):
        self.event = event
        self.condition = condition
        self._groutine = groutine or greenlet.getcurrent() # TODO rename
        self.receiver = self._groutine.parent
    
    def switch(self, value=None):
        # check the condition and call groutine.switch()
        #
        if self.condition and not self.condition(value):
            return
        return self._groutine.switch(value)
    
    def send(self, value=None):
        return self.receiver.switch(value)

    def __enter__(self):
        self.event.listeners.add(self)
        return self
    
    def __exit__(self, *exc_info):
        self.event.listeners.remove(self)
    
    def __repr__(self):
        return 'on %(event)s: %(_groutine)s -> %(receiver)s' % self.__dict__
        
    __str__ = __repr__


class CallListener(Listener):

    def __enter__(self):
        if not self.event.callable_wrapper.patched:
            self.event.callable_wrapper.patch()
        return super(CallListener, self).__enter__()
    
    def __exit__(self, *exc_info):
        super(CallListener, self).__exit__(*exc_info)
        if not self.event.listeners and self.event.callable_wrapper.patched:
            self.event.callable_wrapper.restore()
        

class Event(object):
    '''
    An event is uniquely identified by it's name
    and has a set of listeners.
    '''
    instances = {}
    listener_class = Listener
    
    def __new__(cls, key):
        if key in Event.instances:
            return Event.instances[key]
        return super(Event, cls).__new__(cls)

    def __init__(self, key):
        if key in Event.instances:
            return
        self.key = key
        self.listeners = set()
        Event.instances[key] = self
    
    def fire(self, *args, **kwds):
        '''
        Event is fired with a `value` which can be any object.
        '''
        if kwds:
            assert not args, "Can either specify value to fire or keywords, not both"
            value = kwds
        else:
            try:
                value = args[0]
            except:
                raise AssertionError("Should specify the value to fire")
        
        responses = []
        for listener in tuple(self.listeners):
            listener.receiver = greenlet.getcurrent()
            resp = listener.switch(value)
            responses.append(resp)
        return self.process_responses(responses)
    
    def process_responses(self, values):
        '''
        Process values listeners switch back with
        in response to fired events.
        '''
        for value in values:
            if value is not None: return value
    
    def listen(self, **kwargs):
        '''
        Create a listener. 
        '''
        return self.listener_class(self, **kwargs)
    
    def wait(self, **listener_kwargs):
        '''
        Shortcut. Listens only until the first firing of the event.
        
        Makes values switch with the listener groutine.
        '''
        with self.listen(**listener_kwargs) as lnr:
            return lnr.send()
    
    def __repr__(self):
        return 'Event %s' % self.key
    
    __str__ = __repr__
    
    def __call__(self, **kw):
        return _FiringHelper(self)(**kw)

# TODO rewrite
#@contextmanager
#def listen_any(events, **listener_kwargs):
#    listeners = []
#    for event in events:
#        listener = event.listen(**listener_kwargs)
#        listeners.append(listener)
#        listener.__enter__()
#    yield
#    for listener in listeners:
#        listener.__exit__()
#
#def wait_any(events, **listener_kwargs):
#    with listen_any(events, **listener_kwargs):
#        return switch()


class EventDict(object):
    '''
    OrderedDict, customized for needs of being the value event fires.
    For example, returns values, not keys, when is iterated over.
    '''
    
    ## no-op wrappers
    
    def __init__(self, *args, **kw):
        self._odict = collections.OrderedDict(*args, **kw)

    def __getattr__(self, name):
        return getattr(self._odict, name)

    def __getitem__(self, key):
        return self._odict[key]

    def __setitem__(self, key, item):
        self._odict[key] = item
    
    def __repr__(self):
        return repr(self._odict)
    
    ##
    
    def __iter__(self):
        return iter(self._odict.values())
    
    @classmethod
    def from_function_call(cls, callabl, args, kwargs):
        if getattr(callabl, '__self__', None):
            sig = inspect.signature(callabl.__func__)
            bound_args = sig.bind(callabl.__self__, *args, **kwargs).arguments
        else:
            sig = inspect.signature(callabl)
            bound_args = sig.bind(*args, **kwargs).arguments
        
        instance = cls()
        for name, parameter in sig.parameters.items():
            if name in bound_args:
                instance[name] = bound_args[name]
            elif parameter.default is not inspect._empty:
                instance[name] = parameter.default
        return instance


class _FiringHelper(object):
    '''
    Utility class that allows to write
    
        e = Event('SOME_EVENT')
        e(a=1)(b=2).fire()
    
    '''
    def __init__(self, event):
        self.event = event
        self._value = EventDict()
    
    def fire(self):
        return self.event.fire(self._value)
    
    def __call__(self, **kw):
        self._value.update(kw)
        return self


class CallableWrapper(object):
    '''
    Wraps a callable. Calls respective events (``event``) before and after
    the target call. Events sent differ in ``type`` argument:
    'ENTER' and 'EXIT' respectively.
    '''

    def __init__(self, event, target_container, target_attr):
        self.event = event
        self._target_parent = target_container
        self._target_attribute = target_attr
        self._target = getattr(target_container, target_attr)
        self.patched = False



    def patch(self):
        '''
        Replace original with wrapper.
        '''
        if is_classmethod(self._target):
            target = classmethod(self._target.__func__)
        else:
            target = self._target
        setattr(self._target_parent, self._target_attribute, self(target))
        self.patched = True
    
    def restore(self):
        '''
        Put original callable on it's place back.
        '''
        setattr(self._target_parent, self._target_attribute, self._target)
        self.patched = False
        
    
    @wrapt.function_wrapper
    def __call__(self, wrapped, instance, args, kwargs):
        try:
            #XXX restore ?
            
            event_dict = EventDict.from_function_call(wrapped, args, kwargs)
            if isinstance(self.event, BeforeFunctionCall):
                enter_value = self.event.fire(event_dict)
                if enter_value is not None:
                    return enter_value if enter_value is not ExplicitNone else None

            return_value = wrapped(*args, **kwargs)

            if isinstance(self.event, AfterFunctionCall):
                event_dict['return_value'] = return_value
                exit_value = self.event.fire(event_dict)
                if exit_value is ExplicitNone:
                    return None
                if exit_value is not None:
                    return exit_value
            return return_value
        finally:
            'TODO'


class FunctionCall(Event):
    '''
    Is fired when target callable is called (event's name is callable's
    import path).
    
    `callable_wrapper` is responsible for the respective patching.
    '''

    listener_class = CallListener

    def __init__(self, key):
        if key in Event.instances:
            return
        if isinstance(key, str):
            target_container, target_attr, _ = object_from_name(key) 
        else:
            assert len(key) == 2
            target_container, target_attr = key
        self.callable_wrapper = CallableWrapper(self, target_container,
                                                target_attr)
        # Add to events registry in the end
        super(FunctionCall, self).__init__(key)


    def process_responses(self, values):
        for value in values:
            if isinstance(value, ForceReturn):
                return value.value
        return super(FunctionCall, self).process_responses(values)

    def __repr__(self):
        return 'FCall %s' % self.callable_wrapper._target.__name__
    
    __str__ = __repr__


class BeforeFunctionCall(FunctionCall):
    pass

class AfterFunctionCall(FunctionCall):
    pass


class Groutine(greenlet.greenlet):
    
    def __init__(self, *args, **kwargs):
        super(Groutine, self).__init__(*args, **kwargs)
        self.func = self.run

    def __repr__(self):
        try:
            return '%s: %s' % (self.func.__name__, self.__class__.__name__)
        except Exception as exc:
            print (exc)
            return super(Groutine, self).__repr__()
    
    __str__ = __repr__


## Shortcuts ##


def make_event(key):
    '''
    Utility function that is a shortcut for creating events.
    Tries to guess the event class and instantiates it.
    '''
    if isinstance(key, (tuple, list)) and len(key) == 2:
        return AfterFunctionCall(key)
    
    if isinstance(key, str) and '.' in key:
        if key.startswith('-'):
            return BeforeFunctionCall(key[1:])
        return AfterFunctionCall(key)
    
    return Event(key)

def wait(event, *args, **kw):
    '''
    Shortcut function.
    '''
    if not isinstance(event, Event):
        event = make_event(event)
    return event.wait(*args, **kw)
