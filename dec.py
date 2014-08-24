# -*- coding: utf-8 -*-

'''
Here live decorators and related stuff
'''


from groutines import Groutine

class groutine(object): # -> GroutineCallable
    '''
    Wraps functions supposed to be groutines.
    '''
    def __init__(self, function, event=None, **listener_kwargs):
        self.function = function
        self.event = event
        self.listener_kwargs = listener_kwargs
        self.__name__ = self.function.__name__
    
    @classmethod
    def wrapper(cls, *args, **kwargs):
        return lambda func: cls(func, *args, **kwargs)  
    
    def __repr__(self):
        return '%s groutine function' % self.function.__name__
    
    def __call__(self):
        if not self.event:
            return self.function()
        with self.event.listen(**self.listener_kwargs) as lnr:
            value = lnr.send()
        rv = self.function(*value, **value.__dict__)
        lnr.send(rv)



class loop(groutine):
    
    def __call__(self):
        with self.event.listen(**self.listener_kwargs) as lnr:
            value = lnr.send() 
            while True:
                rv = self.function(*value, **value.__dict__)
                value = lnr.send(rv)

if __name__ == '__main__':
    @groutine.wrapper()
    def f():
        return 1
    f = Groutine(f)
    print (f.switch())
    
    